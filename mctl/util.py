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
import functools
import logging
import os
from typing import Any, Callable, Optional

from mctl.exception import massert

LOG = logging.getLogger(__name__)


def await_sync(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


async def download_url(url: str, dest_path: str) -> None:
    LOG.info("Downloading %s to %s", url, dest_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
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
        command,
        stdout=output_type,
        stderr=output_type,
        cwd=cwd,
        **kwargs,
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


def get_rel_dir_files(directory: str):
    return [
        os.path.relpath(os.path.join(root, f), directory)
        for root, _, files in os.walk(directory)
        for f in files
    ]
