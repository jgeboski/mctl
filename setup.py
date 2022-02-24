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

from setuptools import setup

setup(
    name="mctl",
    version="2.0.1",
    url="https://github.com/jgeboski/mctl",
    author="James Geboski",
    author_email="jgeboski@gmail.com",
    license="MIT",
    description="Minecraft server controller and plugin manager",
    packages=["mctl"],
    install_requires=["aiofiles", "aiohttp", "click", "pyyaml"],
    python_requires=">=3.7",
    entry_points={"console_scripts": ["mctl = mctl.commands:cli"]},
)
