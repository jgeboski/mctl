Name:           mctl
Version:        2.2.1
Release:        1%{?dist}
Summary:        Minecraft server controller and plugin manager.
License:        MIT
URL:            https://github.com/jgeboski/%{name}
Source0:        https://github.com/jgeboski/%{name}/archive/refs/tags/v%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       git
Requires:       python3 >= 3.7
Requires:       python3-aiofiles
Requires:       python3-aiohttp
Requires:       python3-click >= 8
Requires:       python3-pyyaml
Requires:       screen

%description
MCTL is a python tool for automating and reducing the operational cost
of running Minecraft servers. MCTL provides a number of features:
* Management (starting and stopping) of one or more servers.
* Plugin management (building, updating, and snapshotting).
* Fake server when the main server is offline, showing a status message.
* All of this wrapped up in an easy to use CLI.

%prep
%autosetup -p1

%build
%{__python3} setup.py build

%install
%{__python3} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT
install -Dm 0644 completion/mctl.bash \
    $RPM_BUILD_ROOT%{_datadir}/bash-completion/completions/mctl
install -Dm 0644 completion/mctl.fish \
    $RPM_BUILD_ROOT%{_datadir}/fish/completions/mctl.fish
install -Dm 0644 completion/mctl.zsh \
    $RPM_BUILD_ROOT%{_datadir}/zsh/site-functions/_mctl

%files
%doc config.yml LICENSE README.md
%{_bindir}/mctl
%{_datadir}/bash-completion/completions/mctl
%{_datadir}/fish/completions/mctl.fish
%{_datadir}/zsh/site-functions/_mctl
%{python3_sitelib}/mctl/
%{python3_sitelib}/mctl*egg-info/

%changelog
