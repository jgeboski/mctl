#!/usr/bin/env python3

# Copyright 2012-2020 James Geboski <jgeboski@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

import asyncio
from collections import defaultdict
import hashlib
import logging
import os
import re
import time
from typing import DefaultDict, Dict, List, Optional, Tuple

from mctl.config import Config, Package, Server
from mctl.exception import massert
from mctl.util import (
    download_url,
    execute_shell_check,
    find_git_repos,
    get_rel_dir_files,
    git_clone_or_pull,
    git_pull_working_branch,
    git_rev,
)

LOG = logging.getLogger(__name__)


def archive_build(config: Config, package: Package, build_dir: str, rev: str) -> None:
    build_files = get_rel_dir_files(build_dir)
    archive_dir = os.path.join(config.build_path, ".archive")
    for path, pattern in package.artifacts.items():
        matches = [
            build_file for build_file in build_files if pattern.match(build_file)
        ]
        massert(
            len(matches) != 0,
            f"Found no artifacts for package {package.name} matching pattern {pattern}",
        )
        massert(
            len(matches) == 1,
            f"Ambiguous artifact pattern {pattern} for package {package.name}: {matches}",
        )

        match = matches[0]
        artifact_path = os.path.join(build_dir, match)
        root, ext = os.path.splitext(path)
        archive_path = os.path.join(archive_dir, package.name, f"{root}-{rev}{ext}")
        LOG.debug("Archiving artifact %s to %s", artifact_path, archive_path)
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        os.rename(artifact_path, archive_path)


async def combined_git_rev(build_dir: str) -> Optional[str]:
    git_repos = find_git_repos(build_dir)
    LOG.debug("Found %d Git repos in %s: %s", len(git_repos), build_dir, git_repos)
    if len(git_repos) == 0:
        return None

    if len(git_repos) == 1:
        rev = await git_rev(git_repos[0])
        LOG.debug("Using the short hash, %s, for the revision in %s", rev, build_dir)
        return rev

    revs = await asyncio.gather(*[git_rev(repo_dir) for repo_dir in git_repos])
    md5 = hashlib.md5()
    md5.update(":".join(revs).encode("utf-8"))
    hashed = md5.hexdigest()
    rev = hashed[:7]
    LOG.debug(
        "Using the MD5 of all short hashes, %s, for the revision in %s", rev, build_dir
    )
    return rev


async def combined_git_pull(build_dir: str) -> None:
    git_repos = find_git_repos(build_dir)
    LOG.debug("Updating %d all Git repos in %s: ", len(git_repos), build_dir, git_repos)
    await asyncio.gather(*[git_pull_working_branch(repo_dir) for repo_dir in git_repos])


async def package_build(config: Config, package: Package, force: bool = False) -> None:
    LOG.info("Building package %s", package.name)
    build_dir = os.path.join(config.build_path, package.name)
    os.makedirs(build_dir, exist_ok=True)

    if package.repo and package.repo.type == "git":
        LOG.info("Updating Git repo for package %s", package.name)
        await git_clone_or_pull(build_dir, package.repo.url, package.repo.branch)

    rev = await combined_git_rev(build_dir)
    prev_revs = package_revisions(config, package)
    if not force and rev is not None and rev in prev_revs:
        LOG.info(
            "Build of package %s already exists for revision %s, skipping",
            package.name,
            rev,
        )
        return

    if package.fetch_urls:
        LOG.info(
            "Fetching %d URLs for package %s...", len(package.fetch_urls), package.name
        )
        await asyncio.gather(
            *[
                download_url(url, os.path.join(build_dir, path))
                for path, url in package.fetch_urls.items()
            ]
        )

    cmd_count = len(package.build_commands)
    for i, command in enumerate(package.build_commands, 1):
        LOG.info("Executing build command %d of %d: %s", i, cmd_count, command)
        await execute_shell_check(command, hide_ouput=False, cwd=build_dir)

    # Attempt to get an updated revision from all git repos after all
    # build commands have executed. This helps support packages that use
    # scripts to fetch Git repos (ex: Spigot's BuildTools). The build
    # process will update these repos twice. Once up above to make sure
    # the same revision is not being rebuilt. And once here to make sure
    # the revision is accurate.
    rev = await combined_git_rev(build_dir)
    if rev is None:
        rev = str(int(time.time()))

    archive_build(config, package, build_dir, rev)


def package_revisions(
    config: Config, package: Package
) -> Dict[str, Dict[str, Tuple[str, int]]]:
    archive_dir = os.path.join(config.build_path, ".archive", package.name)
    revs: DefaultDict[str, Dict[str, Tuple[str, int]]] = defaultdict(dict)
    for path in package.artifacts:
        path_head, path_tail = os.path.split(path)
        base_dir = os.path.join(archive_dir, path_head)
        if not os.path.exists(base_dir):
            continue

        root, ext = os.path.splitext(path_tail)
        pattern = re.compile(
            fr"{re.escape(root)}\-(?P<rev>[a-zA-Z0-9]+){re.escape(ext)}$"
        )
        with os.scandir(base_dir) as dirit:
            for item in dirit:
                if not item.is_file():
                    continue

                match = pattern.match(item.name)
                if not match:
                    continue

                st = item.stat()
                rev = match.group("rev")
                revs[rev][path] = os.path.join(base_dir, item.name), int(st.st_ctime)

    ret_revs: Dict[str, Dict[str, Tuple[str, int]]] = {}
    required = set(package.artifacts)
    for rev, artifacts in revs.items():
        available = set(artifacts)
        missing = required - available
        if missing:
            LOG.warning(
                "Ignoring revision %s for package %s due to missing artifacts: %s",
                rev,
                package.name,
                missing,
            )
        else:
            ret_revs[rev] = artifacts

    return ret_revs


async def package_upgrade(
    config: Config,
    server: Server,
    package: Package,
    rev: Optional[str] = None,
    force: bool = False,
) -> None:
    revs = package_revisions(config, package)
    massert(revs, f"There are no built revisions for package {package.name}")
    if rev is None:
        rev, _ = sort_revisions_n2o(revs)[0]
        LOG.debug(
            "No revision specified for package %s, using revision %s", package.name, rev
        )
    else:
        massert(rev in revs, f"Unknown revision {rev} for package {package.name}")

    artifacts = revs[rev]
    rand_artifact, _ = list(revs[rev].items())[0]
    rand_path = os.path.join(server.path, rand_artifact)
    current_rev = None
    if os.path.islink(rand_path):
        root, ext = os.path.splitext(os.path.basename(rand_artifact))
        match = re.match(
            fr"{re.escape(root)}\-(?P<rev>[a-zA-Z0-9]+){re.escape(ext)}$",
            os.path.basename(os.readlink(rand_path)),
        )
        if match:
            current_rev = match.group("rev")

        if not force and current_rev == rev:
            LOG.info(
                "Package %s already up-to-date for server %s, skipping",
                package.name,
                server.name,
            )
            return

    LOG.info(
        "Upgrading package %s to revision %s from revision %s",
        package.name,
        rev,
        current_rev,
    )

    for path, info in artifacts.items():
        archive_path, _ = info
        artifact_path = os.path.join(server.path, path)
        if os.path.exists(artifact_path):
            LOG.debug("Removing old artifact %s", artifact_path)
            os.unlink(artifact_path)

        LOG.debug("Linking archived artifact %s to %s", archive_path, artifact_path)
        os.symlink(archive_path, artifact_path)


def sort_revisions_n2o(
    revs: Dict[str, Dict[str, Tuple[str, int]]]
) -> List[Tuple[str, int]]:
    timed_revs = {
        rev: max(artifact[1] for artifact in artifacts.values())
        for rev, artifacts in revs.items()
    }
    return sorted(timed_revs.items(), key=lambda kv: kv[1], reverse=True)
