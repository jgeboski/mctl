#!/usr/bin/env python

from distutils.core import setup

setup(
    name =         "MCTL",
    version =      "0.1.0",
    author =       "jgeboski",
    author_email = "jgeboski@gmail.com",
    url =          "https://github.com/jgeboski/mctl/",
    description =  "Minecraft server controller",
    packages =     ["mctl"],
    scripts =      ["scripts/mctl", "scripts/mctl-fake"],
    classifiers =  [
            "Development Status :: 3 - Alpha",
            "Environment :: Console",
            "Intended Audience :: System Administrators",
            "License :: OSI Approved :: GNU General Public License (GPL)",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Topic :: System :: Systems Administration",
            "Topic :: Utilities"
        ]
)
