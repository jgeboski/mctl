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
import asyncio
import logging
import os
import re
import sys
from typing import Dict, NamedTuple, Optional

from mctl.config import Server
from mctl.exception import massert
from mctl.util import execute_shell_check

LOG = logging.getLogger(__name__)


class ActiveSessions(NamedTuple):
    either: bool
    main: bool
    fake: bool


def get_session_name(server: Server, fake: bool = False) -> str:
    name = f"mctl-{server.name}"
    if fake:
        name = f"{name}-fake"

    return name


async def get_active_sessions(server: Server) -> ActiveSessions:
    stdout = await execute_shell_check("screen -ls", False)
    session_name = get_session_name(server)
    match = re.search(rf"^\s*\d+\.{session_name}\b", stdout, re.MULTILINE)
    fake_session_name = get_session_name(server, True)
    fake_match = re.search(rf"^\s*\d+\.{fake_session_name}\b", stdout, re.MULTILINE)

    main = bool(match)
    fake = bool(fake_match)
    return ActiveSessions(either=main or fake, main=main, fake=fake)


async def server_execute(server: Server, command: str) -> None:
    active_sessions = await get_active_sessions(server)
    massert(active_sessions.main, f"Server {server.name} not running")
    session_name = get_session_name(server)
    await execute_shell_check(f"screen -S '{session_name}' -p 0 -X stuff '{command}\n'")


async def server_properties(server: Server) -> Dict[str, str]:
    props_file = os.path.join(server.path, "server.properties")
    massert(
        os.access(props_file, os.R_OK),
        f"server.properties for server {server.name} not readable",
    )

    props: Dict[str, str] = {}
    async with aiofiles.open(props_file) as fp:
        # For whatever reason, "async for line in fp" does not work with
        # aiofiles-0.3.2 and python-3.7.5.
        for line in await fp.readlines():
            line = line.strip()
            if line.startswith("#"):
                continue

            kv = line.split("=", 1)
            key = kv[0].strip()
            if key:
                props[key] = kv[1] if len(kv) > 1 else ""

    return props


async def server_start(server: Server) -> None:
    active_sessions = await get_active_sessions(server)
    massert(not active_sessions.main, f"Server {server.name} already running")
    if active_sessions.fake:
        await server_stop_fake(server)

    session_name = get_session_name(server)
    LOG.info("Starting server %s with screen session %s", server.name, session_name)
    await execute_shell_check(
        f"screen -S '{session_name}' -dm {server.command}", cwd=server.path
    )


async def server_start_fake(server: Server, message: Optional[str] = None) -> None:
    active_sessions = await get_active_sessions(server)
    massert(not active_sessions.either, f"Server {server.name} already running")
    session_name = get_session_name(server, True)
    LOG.info(
        "Starting fake server %s with screen session %s", server.name, session_name
    )

    props = await server_properties(server)
    cmdargs = [sys.argv[0], "fake-server"]
    server_ip = props.get("server-ip")
    if server_ip:
        cmdargs.append(f"--listen-address='{server_ip}'")

    icon_file = os.path.join(server.path, "server-icon.png")
    if os.path.exists(icon_file):
        cmdargs.append(f"--icon-file='{icon_file}'")

    if message:
        cmdargs.append(f"--message='{message}'")

    motd = props.get("motd")
    if motd:
        cmdargs.append(f"--motd='[Server Offline] {motd}'")

    server_port = props.get("server-port")
    if server_port:
        cmdargs.append(f"--port='{server_port}'")

    command = " ".join(cmdargs)
    await execute_shell_check(f"screen -S '{session_name}' -dm {command}")


async def server_stop(server: Server, message: Optional[str]) -> None:
    active_sessions = await get_active_sessions(server)
    if active_sessions.fake:
        await server_stop_fake(server)
        return

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
    await execute_shell_check(f"screen -S '{session_name}' -x", throw_on_error=False)


async def server_stop_fake(server: Server):
    active_sessions = await get_active_sessions(server)
    massert(active_sessions.fake, f"Fake server {server.name} not running")
    LOG.info("Stopping fake server %s", server.name)
    session_name = get_session_name(server, True)
    await execute_shell_check(f"screen -S '{session_name}' -X quit")
    await execute_shell_check(f"screen -S '{session_name}' -x", throw_on_error=False)
