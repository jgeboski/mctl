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

import aiofiles
import aiohttp
import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

from mctl.exception import massert, MctlError

LOG = logging.getLogger(__name__)


async def download_url(url: str, dest_path: str) -> None:
    LOG.info(f"Downloading %s to %s", url, dest_path)
    os.makedirs(os.path.basename(dest_path), exist_ok=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as res, aiofiles.open(dest_path, mode="wb") as fp:
            massert(res.status == 200, f"Failed to download {url}: HTTP {res.status}")
            while True:
                data = await res.content.read(1024)
                if not data:
                    break

                await fp.write(data)

    LOG.info("Downloaded %s to %s", url, dest_path)


async def execute_shell_check(
    command: str,
    throw_on_error: bool = True,
    hide_ouput=True,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> str:
    if cwd is None:
        cwd = os.getcwd()

    LOG.debug("Executing shell command: '%s' in %s", command, cwd)
    output_type = asyncio.subprocess.PIPE if hide_ouput else None
    proc = await asyncio.create_subprocess_shell(
        command, stdout=output_type, stderr=output_type, cwd=cwd, **kwargs,
    )

    if hide_ouput:
        stdout, stderr = await proc.communicate()
        output = stdout.decode("utf-8")
        LOG.debug("Stdout: %s", output)
        LOG.debug("Stderr: %s", stderr.decode("utf-8"))
    else:
        await proc.wait()
        output = ""

    massert(
        not throw_on_error or proc.returncode == 0,
        f"Failed to execute shell command: '{command}' in {cwd}",
    )
    LOG.debug("Successfully executed shell command: '%s' in %s", command, cwd)
    return output


def find_git_repos(base_dir: str) -> List[str]:
    git_repos = set()
    for git_repo, dir_names, _ in os.walk(base_dir):
        if ".git" not in dir_names:
            continue

        parent_dir = os.path.dirname(git_repo)
        if parent_dir and parent_dir in git_repos:
            LOG.debug("Ignoring sub Git repo %s", _)
            continue

        git_repos.add(git_repo)

    LOG.debug("Found %d Git repos in %s: %s", len(git_repos), base_dir, git_repos)
    return sorted(git_repos)


def get_rel_dir_files(directory: str):
    return [
        os.path.relpath(os.path.join(root, f), directory)
        for root, _, files in os.walk(directory)
        for f in files
    ]


async def git_clone_or_pull(repo_dir: str, url: str, branch: str = "master") -> None:
    git_path = os.path.join(repo_dir, ".git")
    if os.path.exists(git_path):
        LOG.debug("Updating existing Git repo %s", repo_dir)
        await execute_shell_check("git clean -dfx", cwd=repo_dir)
        await execute_shell_check("git pull", cwd=repo_dir)
    else:
        LOG.debug("Cloning new Git repo %s", repo_dir)
        await execute_shell_check(f"git clone '{url}' '{repo_dir}'")

    LOG.debug("Updating to Git repo %s to branch %s", repo_dir, branch)
    await execute_shell_check(f"git checkout {branch}", cwd=repo_dir)


async def git_pull_working_branch(repo_dir: str) -> None:
    LOG.debug("Updating Git repo %s on existing branch", repo_dir)
    await execute_shell_check("git clean -dfx", cwd=repo_dir)
    await execute_shell_check("git pull", cwd=repo_dir)


async def git_rev(repo_dir: str) -> str:
    rev = await execute_shell_check("git rev-parse --short HEAD", cwd=repo_dir)
    rev = rev.strip()
    LOG.debug("Got git revision %s for repo %s", rev, repo_dir)
    return rev
