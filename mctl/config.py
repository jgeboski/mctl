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
import aiofiles
import os
import re
from typing import Any, Dict, IO, List, Mapping, Optional, Union
from urllib.parse import urlparse
import yaml

from mctl.exception import massert, MctlError


def dump_config_object_to_lines(
    config_object: Union[dict, object], offset: int = 0
) -> List[str]:
    if isinstance(config_object, ConfigObject):
        kvitems = vars(config_object).items()
    elif isinstance(config_object, dict):
        kvitems = config_object.items()
    else:
        return []

    lines = []
    indent = "  " * offset
    for key, value in sorted(kvitems, key=lambda kv: kv[0]):
        if key == "config_dict":
            continue

        if isinstance(value, (dict, ConfigObject)):
            lines.append(f"{indent}{key}:")
            lines.extend(dump_config_object_to_lines(value, offset + 1))
        elif isinstance(value, list):
            lines.append(f"{indent}{key}: {sorted(value)}")
        else:
            lines.append(f"{indent}{key}: {value}")

    return lines


class ConfigObject(ABC):
    def __init__(self, config_dict: Dict[str, Any]) -> None:
        self.config_dict = config_dict

    def __str__(self) -> str:
        return os.linesep.join(dump_config_object_to_lines(self))

    @abstractmethod
    def validate(self) -> None:
        raise NotImplementedError()

    def get_value(self, name: str, default: Optional[Any] = None) -> Any:
        value = self.config_dict.get(name, default)
        massert(value is not None, f"Expected a config value for {name}")
        return value

    def get_dict(self, name: str, default: Optional[Any] = None) -> Dict[str, Any]:
        value = self.get_value(name, default)
        massert(
            isinstance(value, Mapping) and all(isinstance(key, str) for key in value),
            f"Expected a map with string keys for config value {name}, got: {value}",
        )
        return value

    def get_int(self, name: str, default: Optional[Any] = None) -> int:
        value = self.get_value(name, default)
        massert(
            isinstance(value, int),
            f"Expected a integer for config value {name}, got: {value}",
        )
        return value

    def get_str(self, name: str, default: Optional[Any] = None) -> str:
        value = self.get_value(name, default)
        massert(
            isinstance(value, str),
            f"Expected a string for config value {name}, got: {value}",
        )
        return value

    def get_str_list(self, name: str, default: Optional[Any] = None) -> List[str]:
        value = self.get_value(name, default)
        massert(
            isinstance(value, List) and all(isinstance(val, str) for val in value),
            f"Expected a list of strings for config value {name}, got: {value}",
        )
        return value


class Repository(ConfigObject):
    def __init__(self, config_dict: Dict[str, Any], name: str) -> None:
        super().__init__(config_dict)
        self.name = name
        self.url = self.get_str("url")
        self.type = self.get_str("type").lower()
        self.branch = self.get_str("branch")

    def validate(self) -> None:
        massert(
            self.type == "git",
            f"Unsupported repository type {self.type} for repo {self.name}",
        )


class Package(ConfigObject):
    def __init__(self, config_dict: Dict[str, Any], name: str) -> None:
        super().__init__(config_dict)
        self.name = name
        self.repositories = {
            name: Repository(repo, name)
            for name, repo in self.get_dict("repositories", {}).items()
        }
        self.fetch_urls = self.get_dict("fetch-urls", {})
        self.build_commands = self.get_str_list("build-commands")
        self.artifacts: Dict[str, re.Pattern] = {}

        for path, regex in self.get_dict("artifacts").items():
            if not regex.endswith("$"):
                regex += "$"

            try:
                pattern = re.compile(regex)
            except Exception:
                raise Exception(f"Invalid artifact regex: {regex}")

            self.artifacts[path] = pattern

    def validate(self) -> None:
        massert(self.name != ".archive", f"Package cannot be named .archive")
        massert(
            self.repositories or self.fetch_urls,
            f"Package {self.name} missing repositories or fetch URLs",
        )
        massert(self.build_commands, f"Package {self.name} missing build commands")
        massert(self.artifacts, f"Package {self.name} missing artifacts")

        for repo in self.repositories.values():
            repo.validate()


class Server(ConfigObject):
    def __init__(self, config_dict: Dict[str, Any], name: str) -> None:
        super().__init__(config_dict)
        self.name = name
        self.path = self.get_str("path")
        self.command = self.get_str("command")
        self.stop_timeout = self.get_int("stop-timeout", 60)
        self.packages = self.get_str_list("packages")

    def validate(self) -> None:
        massert(
            self.stop_timeout >= 0,
            f"Server {self.name} stop timeout must be >= 0: {self.stop_timeout}",
        )
        massert(self.packages, f"Server {self.name} missing packages")


class Config(ConfigObject):
    def __init__(self, config_dict: Dict[str, Any]) -> None:
        super().__init__(config_dict)
        self.data_path = self.get_str("data-path")
        self.build_niceness = self.get_int("build-niceness", 15)
        self.max_package_revisions = self.get_int("max-package-revisions", 5)
        self.servers = {
            name: Server(server, name)
            for name, server in self.get_dict("servers").items()
        }
        self.packages = {
            name: Package(package, name)
            for name, package in self.get_dict("packages").items()
        }

    def validate(self) -> None:
        massert(
            self.build_niceness >= -20 and self.build_niceness <= 19,
            f"Invalid build niceness ([-20, 19]): {self.build_niceness}",
        )
        massert(
            self.max_package_revisions >= 1,
            f"Invalid max package revisions (>= 1): {self.max_package_revisions}",
        )
        massert(self.servers, f"No servers defined")
        massert(self.servers, f"No packages defined")

        for package in self.packages.values():
            package.validate()

        for server in self.servers.values():
            server.validate()
            for package_name in server.packages:
                massert(package_name in self.packages, f"Undefined package: {package}")

    def get_package(self, name: str) -> Package:
        massert(name in self.packages, f"Undefined package: {name}")
        return self.packages[name]

    def get_server(self, name: str) -> Server:
        massert(name in self.servers, f"Undefined server: {name}")
        return self.servers[name]


async def load_config(config_file: str) -> Config:
    try:
        async with aiofiles.open(config_file) as fp:
            config_text = await fp.read()
    except OSError as ex:
        raise MctlError(f"Failed to read {config_file}: {ex}")

    config_dict = yaml.load(config_text)
    massert(config_dict, "Empty or missing config")
    config = Config(config_dict)
    config.validate()
    return config
