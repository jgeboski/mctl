#!/usr/bin/env python

# Copyright 2012-2013 James Geboski <jgeboski@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from distutils.command.install import install
from distutils.core            import setup
from distutils.util            import convert_path

class mctl_install(install):
    description = "Custom Install Process"

    user_options = install.user_options
    user_options.extend([
        ('install-man=',        None,
            'installation directory for man documentation'),
        ('install-completion=', None,
            'installation directory for completion scripts')
    ])

    def initialize_options(self):
        install.initialize_options(self)

        self.install_completion = None
        self.install_man        = None

    def finalize_options(self):
        install.finalize_options(self)

        if not isinstance(self.distribution.data_files, list):
            self.distribution.data_files = list()

        if self.install_completion:
            self.distribution.data_files.append(
                (self.install_completion,
                    ['scripts/completion/mctl',
                     'scripts/completion/mctl-fake'])
            )

        if self.install_man:
            man1 = os.path.join(self.install_man, "man1")

            self.distribution.data_files.append(
                (man1, ['man/mctl.1', 'man/mctl-fake.1'])
            )

setup(
    name         = "mctl",
    version      = "0.1.0",
    author       = "jgeboski",
    author_email = "jgeboski@gmail.com",
    url          = "https://github.com/jgeboski/mctl/",
    description  = "Minecraft server controller",
    packages     = ["mctl"],
    scripts      = ["scripts/mctl", "scripts/mctl-fake"],
    cmdclass     = {'install': mctl_install},
    classifiers  = [
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
