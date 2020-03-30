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
import logging
from typing import Any, Dict

from mctl.exception import massert, MctlError

LOG = logging.getLogger(__name__)


async def execute_shell_check(
    command: str, throw_on_error: bool = True, **kwargs: Any
) -> str:
    LOG.debug("Executing shell command: %s", command)
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,
    )
    stdout, stderr = await proc.communicate()
    LOG.debug("Stdout: %s", stdout.decode("utf-8"))
    LOG.debug("Stderr: %s", stderr.decode("utf-8"))

    massert(
        not throw_on_error or proc.returncode == 0,
        f"Failed to execute shell command: {command}",
    )
    LOG.debug("Successfully executed shell command: %s", command)
    return stdout.decode("utf-8")
