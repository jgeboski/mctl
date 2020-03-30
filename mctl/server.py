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
import os
import re
from typing import Optional

from mctl.config import Server
from mctl.exception import massert
from mctl.util import execute_shell_check

LOG = logging.getLogger(__name__)


def get_session_name(server: Server) -> str:
    return f"mctl-{server.name}"


async def is_session_active(server: Server) -> bool:
    stdout = await execute_shell_check("screen -ls", False)
    session_name = get_session_name(server)
    match = re.search(rf"^\s*\d+\.{session_name}\s*", stdout, re.MULTILINE)
    return bool(match)


async def server_execute(server: Server, command: str) -> None:
    massert(await is_session_active(server), f"Server {server.name} not running")
    session_name = get_session_name(server)
    await execute_shell_check(f"screen -S '{session_name}' -p 0 -X stuff '{command}\n'")


async def server_start(server: Server) -> None:
    massert(
        not await is_session_active(server), f"Server {server.name} already running"
    )
    session_name = get_session_name(server)
    LOG.info("Starting server %s with screen session %s", server.name, session_name)
    await execute_shell_check(
        f"screen -S '{session_name}' -dm {server.command}", cwd=server.path
    )


async def server_stop(server: Server, message: Optional[str]) -> None:
    session_name = get_session_name(server)
    seconds_left = server.stop_timeout
    while seconds_left > 0:
        say_msg = f"say Server stopping in {seconds_left} seconds"
        if message:
            say_msg += f": {message}"

        LOG.info("Server %s stopping in %d seconds", server.name, seconds_left)
        await server_execute(server, say_msg)
        wait_seconds = 5 if seconds_left >= 10 else 1
        seconds_left -= wait_seconds
        await asyncio.sleep(wait_seconds)

    LOG.info("Stopping server %s", server.name)
    await server_execute(server, "say Server stopping.")
    await server_execute(server, "save-all")
    await server_execute(server, "stop")
    LOG.info("Waiting for server %s to stop", server.name)
    await execute_shell_check(f"screen -S '{session_name}' -x")
