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

from abc import ABC, abstractmethod
import asyncio
import hashlib
from inspect import isclass
import logging
import os
from typing import List, Iterable, Optional, Type

from mctl.config import Repository
from mctl.exception import massert, MctlError
from mctl.util import execute_shell_check

LOG = logging.getLogger(__name__)


class ScmRepository(object):
    @staticmethod
    @abstractmethod
    def type_name() -> str:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    async def find_all_dirs(base_dir: str) -> List[str]:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    async def revision(repo_dir: str) -> str:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    async def update(
        repo_dir: str, url: Optional[str] = None, branch: Optional[str] = None
    ) -> None:
        raise NotImplementedError()


class GitRepository(ScmRepository):
    @staticmethod
    def type_name() -> str:
        return "git"

    @staticmethod
    async def find_all_dirs(base_dir: str) -> List[str]:
        repos = set()
        for git_repo, dir_names, _ in os.walk(base_dir):
            if ".git" not in dir_names:
                continue

            parent_dir = os.path.dirname(git_repo)
            if parent_dir and parent_dir in repos:
                LOG.debug("Ignoring sub Git repo %s", _)
                continue

            repos.add(git_repo)

        LOG.debug("Found %d Git repos in %s: %s", len(repos), base_dir, repos)
        return sorted(repos)

    @staticmethod
    async def revision(repo_dir: str) -> str:
        rev = await execute_shell_check("git rev-parse --short HEAD", cwd=repo_dir)
        rev = rev.strip()
        LOG.debug("Got git revision %s for repo %s", rev, repo_dir)
        return rev

    @staticmethod
    async def update(
        repo_dir: str, url: Optional[str] = None, branch: Optional[str] = None
    ) -> None:
        git_path = os.path.join(repo_dir, ".git")
        if os.path.exists(git_path):
            LOG.debug("Updating Git repo %s on working branch", repo_dir)
            await execute_shell_check("git reset --hard", cwd=repo_dir)
            await execute_shell_check("git clean -dfx", cwd=repo_dir)
            await execute_shell_check("git pull", cwd=repo_dir)
        elif url:
            LOG.debug("Cloning new Git repo %s", repo_dir)
            await execute_shell_check(f"git clone '{url}' '{repo_dir}'")
        else:
            raise MctlError(
                f"No existing repository or URL for repository in {repo_dir}"
            )

        if branch:
            LOG.debug("Updating to Git repo %s to branch %s", repo_dir, branch)
            await execute_shell_check(f"git checkout {branch}", cwd=repo_dir)


REPOSITORY_TYPES = {
    klass.type_name(): klass
    for klass in globals().values()
    if isclass(klass) and klass != ScmRepository and issubclass(klass, ScmRepository)
}


def get_repo_type(repository: Repository) -> Type[ScmRepository]:
    type_name = repository.type.lower()
    massert(
        type_name in REPOSITORY_TYPES,
        f"Unknown repository type {repository.type} for {repository.name}",
    )
    return REPOSITORY_TYPES[type_name]


async def unified_repo_revision(
    base_dir: str, repositories: Iterable[Repository]
) -> Optional[str]:
    repo_types = REPOSITORY_TYPES.values()
    all_repo_dirs = await asyncio.gather(
        *[repo_type.find_all_dirs(base_dir) for repo_type in repo_types]
    )
    for repo in repositories:
        exists = any(
            os.path.samefile(repo_dir, os.path.join(base_dir, repo.name))
            for repo_dirs in all_repo_dirs
            for repo_dir in repo_dirs
        )
        # These checks should never fail, but it's good to sanity check
        massert(exists, f"Directory for repository {repo.name} missing")

    if not all_repo_dirs:
        return None

    revs = await asyncio.gather(
        *[
            repo_type.revision(repo_dir)
            for repo_type, repo_dirs in zip(repo_types, all_repo_dirs)
            for repo_dir in repo_dirs
        ]
    )

    if len(revs) == 1:
        rev = revs[0]
        LOG.debug("Using the short hash, %s, for the revision in %s", rev, base_dir)
        return revs[0]

    md5 = hashlib.md5()
    md5.update(":".join(revs).encode("utf-8"))
    hashed = md5.hexdigest()
    rev = hashed[:7]
    LOG.debug(
        "Using the MD5 of all short hashes, %s, for the revision in %s", rev, base_dir
    )
    return rev


async def update_all_repos(base_dir: str, repositories: Iterable[Repository]) -> None:
    repo_map = {os.path.join(base_dir, repo.name): repo for repo in repositories}
    if repo_map:
        await asyncio.gather(
            *[
                get_repo_type(repo).update(repo_dir, repo.url, repo.branch)
                for repo_dir, repo in repo_map.items()
            ]
        )

    repo_types = REPOSITORY_TYPES.values()
    all_repo_dirs = await asyncio.gather(
        *[repo_type.find_all_dirs(base_dir) for repo_type in repo_types]
    )

    update_coros = []
    for repo_type, repo_dirs in zip(repo_types, all_repo_dirs):
        for repo_dir in repo_dirs:
            updated = any(
                os.path.samefile(updated_dir, repo_dir) for updated_dir in repo_map
            )
            if not updated:
                update_coros.append(repo_type.update(repo_dir))
            else:
                LOG.info("Repository %s already updated, skipping", repo_dir)

    if update_coros:
        await asyncio.gather(*update_coros)
