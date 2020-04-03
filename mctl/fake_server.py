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
import copy
import base64
import functools
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from mctl.exception import MctlError
from mctl.favicons import CAUTION_BASE64

DEFAULT_MESSAGE = "The server is currently offline!"
DEFAULT_MOTD = "Server Offline!"
DEFAULT_PORT = 25565
LOG = logging.getLogger(__name__)


class ProtocolError(MctlError):
    pass


async def pack_and_send(
    writer: asyncio.StreamWriter, packet_id: int, *args: bytes
) -> None:
    data = pack_varint(packet_id)
    for arg in args:
        data += arg

    data = pack_varint(len(data)) + data
    writer.write(data)


def pack_varint(value: int) -> bytes:
    if value == 0:
        return b"\x00"

    data: List[int] = []
    while value != 0:
        byte = value & 0x7F
        # Logical right shift
        value = (value % (1 << 32)) >> 7
        if value != 0:
            byte |= 0x80

        data.append(byte)

    return bytes(data)


def pack_str(value: str) -> bytes:
    data = value.encode("utf-8")
    return pack_varint(len(data)) + data


async def read_varint(reader: asyncio.StreamReader) -> int:
    value = 0
    byte = 0x80
    bytes_read = 0
    while (byte & 0x80) != 0:
        data = await reader.read(1)
        if not data or len(data) != 1:
            raise ProtocolError("Failed first varint byte")

        byte = data[0]
        value |= (byte & 0x7F) << (bytes_read * 7)
        bytes_read += 1
        if bytes_read > 5:
            raise ProtocolError("Malformed varint")

    return value


def unpack_short(data: bytes) -> Tuple[bytes, int]:
    if len(data) < 2:
        raise ProtocolError("Failed to read short value")

    value = (data[0] << 8) | data[1]
    return data[2:], value


def unpack_str(data: bytes) -> Tuple[bytes, str]:
    data, length = unpack_varint(data)
    if len(data) < length:
        raise ProtocolError("String too long for packet")

    value = data[:length].decode("utf-8")
    return data[length:], value


def unpack_varint(data: bytes) -> Tuple[bytes, int]:
    value = 0
    byte = 0x80
    bytes_read = 0
    while (byte & 0x80) != 0:
        if len(data) < 1:
            raise ProtocolError("Failed first varint bytte")

        byte = data[0]
        data = data[1:]
        value |= (byte & 0x7F) << (bytes_read * 7)
        bytes_read += 1
        if bytes_read > 5:
            raise ProtocolError("Malformed varint")

    # At or over bit 31 (sign bit) means it's a negative number
    if value >= 1 << 31:
        value -= 1 << 32

    return data, value


async def handle_packet(reader: asyncio.StreamReader) -> Tuple[bytes, int]:
    length = await read_varint(reader)
    # Comparison against an arbitrary number to avoid a memory DoS
    if length > 2048:
        raise ProtocolError("Packet too large")

    packet_data = await reader.read(length)
    if length < 1 or len(packet_data) != length:
        raise ProtocolError("Failed to read all packet data")

    return unpack_varint(packet_data)


async def handle_ping(
    packet_data: bytes, writer: asyncio.StreamWriter, ping_response: Dict[str, Any]
) -> None:
    client_addr, _ = writer.get_extra_info("peername")
    packet_data, client_version = unpack_varint(packet_data)
    packet_data, with_addr = unpack_str(packet_data)
    packet_data, with_port = unpack_short(packet_data)
    packet_data, next_state = unpack_varint(packet_data)
    LOG.info(
        "Client %s %s via address %s on port %d using version %d",
        client_addr,
        "pinged" if next_state == 1 else "logged in",
        with_addr,
        with_port,
        client_version,
    )

    ping_response = copy.deepcopy(ping_response)
    ping_response["version"]["protocol"] = client_version
    ping_json = json.dumps(ping_response)
    await pack_and_send(writer, 0, pack_str(ping_json))
    writer.close()


async def connection_handler(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    ping_response: Dict[str, Any],
) -> None:
    client_addr, _ = writer.get_extra_info("peername")
    LOG.debug("New connection from %s", client_addr)
    try:
        packet_data, packet_id = await handle_packet(reader)
        if packet_id == 0:
            await handle_ping(packet_data, writer, ping_response)
        else:
            raise ProtocolError(f"Unsupported packet ID 0x{packet_id:20x}")
    except ProtocolError as ex:
        LOG.error("Client %s requests errored: %s", client_addr, ex)

    writer.close()


async def run_fake_server(
    listen_address: Optional[str] = None,
    port: int = DEFAULT_PORT,
    message: str = DEFAULT_MESSAGE,
    motd: str = DEFAULT_MOTD,
    icon_file: Optional[str] = None,
) -> None:
    try:
        async with aiofiles.open(icon_file, "rb") as fp:
            icon_png_bytes = await fp.read()
    except OSError as ex:
        raise MctlError(f"Failed to read {icon_file}: {ex}")

    icon_png_base64 = (
        base64.b64encode(icon_png_bytes) if icon_png_bytes else CAUTION_BASE64
    )
    ping_response = {
        "version": {"name": "MCTL", "protocol": 0},
        "players": {"max": 0, "online": 0,},
        "description": {"text": motd},
        "text": message,
        "bold": "true",
        "favicon": f"data:image/png;base64,{icon_png_base64}",
    }

    LOG.info("Starting fake-server on %s, port %d", listen_address, port)
    conn_cb = functools.partial(connection_handler, ping_response=ping_response)
    server = await asyncio.start_server(conn_cb, listen_address, port)
    async with server:
        await server.serve_forever()
