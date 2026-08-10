#!/usr/bin/env python3
"""Windows ops documentation collector and renderer."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import unicodedata
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

# Processes whose presence indicates an active VPN or local proxy
PROXY_PROCESS_NAMES = {
    "clash", "clash-verge", "clash-verge-rev", "mihomo",
    "v2ray", "xray", "trojan", "trojan-go",
    "wireguard", "wireguard-nt",
    "openvpn", "openvpn-gui",
    "shadowsocks", "ss-local", "sslocal",
    "sstap", "netch", "sing-box",
    # Fortinet
    "forticlient", "fortisslvpndaemon", "fortivpn", "fortisvn",
    # UniVPN / enterprise VPN
    "univpn", "univpnpromoteservice", "univpnservice",
    # Other enterprise
    "anyconnect", "vpnui", "vpnagent", "zscaler",
}

# Ports commonly used by local proxy/VPN processes
PROXY_PORTS = {7890, 7891, 7892, 1080, 1081, 10808, 10809, 10810, 8080, 8118, 3128}

# Chocolatey rows that are runtime/dependency noise rather than manually
# installed CLI tools. Matches the "no dependency-only packages" rule in
# references/windows/software-detection-rules.md.
_CHOCO_NOISE_EXACT = {
    "chocolatey",
    "chocolatey-compatibility.extension",
    "chocolatey-core.extension",
    "chocolatey-dotnetfx.extension",
    "chocolatey-visualstudio.extension",
    "chocolatey-windowsupdate.extension",
    "dotnetfx",
    "visualstudio-installer",
}
# Upper bound on winget rows kept in the docs. Exceeding it is reported in the
# output rather than silently dropped.
_WINGET_MAX = 300

# winget package ids that are shared runtimes/redistributables pulled in as
# dependencies, not tools someone installed on purpose.
_WINGET_NOISE_PATTERNS = (
    re.compile(r"^Microsoft\.VCRedist\.", re.IGNORECASE),
    re.compile(r"^Microsoft\.VCLibs\.", re.IGNORECASE),
    re.compile(r"^Microsoft\.UI\.Xaml\.", re.IGNORECASE),
    re.compile(r"^Microsoft\.DotNet\.(Native|DesktopRuntime|AspNetCore|HostingBundle|Runtime)", re.IGNORECASE),
    re.compile(r"^Microsoft\.WindowsAppRuntime", re.IGNORECASE),
    re.compile(r"^Microsoft\.EdgeWebView", re.IGNORECASE),
)

_CHOCO_NOISE_PATTERNS = (
    re.compile(r"^KB\d+$", re.IGNORECASE),          # Windows update payloads
    re.compile(r"^vcredist", re.IGNORECASE),        # VC++ redistributables
    re.compile(r"\.extension$", re.IGNORECASE),     # chocolatey helper extensions
    re.compile(r"\.install$", re.IGNORECASE),       # packaging split artefacts
    re.compile(r"\.portable$", re.IGNORECASE),
)

# Windows built-in service name prefixes to suppress
_SYSTEM_SERVICE_NAMES = {
    "ALG", "AppID", "AppIDSvc", "AppInfo", "AppMgmt", "AppReadiness",
    "AppXSvc", "AudioEndpointBuilder", "Audiosrv",
    "BFE", "BITS", "BrokerInfrastructure", "Browser",
    "CDPSvc", "CertPropSvc", "ClipSVC", "COMSysApp",
    "CoreMessagingRegistrar", "CryptSvc",
    "DcomLaunch", "defragsvc", "DeviceAssociationService",
    "DeviceInstall", "Dhcp", "DiagTrack", "DispBrokerDesktopSvc",
    "Dnscache", "DoSvc", "DPS", "DsmSvc", "DusmSvc",
    "EapHost", "EventLog", "EventSystem",
    "Fax", "fdPHost", "FDResPub", "FontCache",
    "gpsvc", "GraphicsPerfSvc",
    "hidserv", "HvHost",
    "icssvc", "IKEEXT", "iphlpsvc",
    "KeyIso", "KtmRm",
    "LanmanServer", "LanmanWorkstation", "lfsvc",
    "LicenseManager", "lltdsvc", "lmhosts", "LSM", "LxpSvc",
    "MapsBroker", "MpsSvc", "MSDTC", "MSiSCSI", "msiserver",
    "NcaSvc", "NcbService", "Netlogon", "Netman", "netprofm",
    "NetSetupSvc", "NlaSvc", "nsi",
    "OneSyncSvc",
    "p2pimsvc", "p2psvc", "PcaSvc", "PerfHost", "PhoneSvc",
    "PimIndexMaintenanceSvc", "pla", "PlugPlay", "PolicyAgent", "Power",
    "PrintNotify", "ProfSvc",
    "RasAuto", "RasMan", "RemoteAccess", "RemoteRegistry",
    "RmSvc", "RpcEptMapper", "RpcSs",
    "SamSs", "Schedule", "SCPolicySvc", "SDRSVC", "seclogon",
    "SENS", "SensorDataService", "SensorService", "SensrSvc",
    "SessionEnv", "SharedAccess", "ShellHWDetection",
    "Spooler", "sppsvc", "SSDPSRV", "SstpSvc", "StateRepository",
    "stisvc", "StorSvc", "svsvc", "swprv", "SysMain",
    "SystemEventsBroker",
    "TabletInputService", "TapiSrv", "TermService", "Themes",
    "TieringEngineService", "TimeBrokerSvc", "TokenBroker", "TrkWks",
    "TrustedInstaller", "tzautoupdate",
    "UdkUserSvc", "uhssvc", "UmRdpService", "UnistoreSvc",
    "upnphost", "UserDataSvc", "UserManager", "UsoSvc",
    "VaultSvc", "vds",
    "vmicguestinterface", "vmicheartbeat", "vmickvpexchange",
    "vmicrdv", "vmicshutdown", "vmictimesync", "vmicvss", "VSS",
    "W32Time", "WaaSMedicSvc", "wbengine", "WbioSrvc",
    "Wcmsvc", "WdiServiceHost", "WdiSystemHost", "WebClient",
    "Wecsvc", "WEPHOSTSVC", "wercplsupport", "WerSvc", "WiaRpc",
    "WinDefend", "WinHttpAutoProxySvc", "Winmgmt", "WinRM",
    "WlanSvc", "wlidsvc", "wlpasvc", "wmiApSrv", "WMPNetworkSvc",
    "WpnService", "WpnUserService", "wscsvc", "WSearch",
    "wuauserv", "wudfsvc",
    "XblAuthManager", "XblGameSave", "XboxGipSvc", "XboxNetApiSvc",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_ps(cmd: str, timeout: int = 30) -> str:
    utf8_prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", utf8_prefix + cmd],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _resolve_exe(name: str) -> str | None:
    """Resolve a command to a concrete path.

    Many Windows dev tools ship as ``.cmd``/``.bat`` shims (npm, scoop, yarn).
    ``subprocess`` without a shell cannot launch a bare ``npm``, so resolve
    through PATH/PATHEXT first and hand CreateProcess a full path.
    """
    return shutil.which(name)


def _run_cmd(args: list[str], timeout: int = 30) -> str:
    if not args:
        return ""
    resolved = _resolve_exe(args[0])
    if resolved is None:
        return ""
    try:
        r = subprocess.run(
            [resolved, *args[1:]], capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _ps_json(cmd: str, timeout: int = 30) -> list[dict]:
    raw = _run_ps(cmd, timeout)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [data] if isinstance(data, dict) else data
    except json.JSONDecodeError:
        return []


def _docs_home() -> Path:
    for var in ("WIN_OPS_DOCS_HOME", "OPS_DOCS_HOME"):
        v = os.environ.get(var)
        if v:
            return Path(v)
    # Reuse existing Linux-convention directory if present
    legacy = Path.home() / ".ops-doc-maintainer-docs"
    if legacy.exists():
        return legacy
    return Path.home() / ".win-ops-doc-maintainer-docs"


def _hostname() -> str:
    return socket.gethostname()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Network collection
# ---------------------------------------------------------------------------

def _adapters() -> list[dict]:
    items = _ps_json(
        "Get-NetAdapter | Select-Object Name, Status, MacAddress, InterfaceDescription"
        " | ConvertTo-Json -Depth 2"
    )
    result = []
    for item in items:
        name = item.get("Name", "")
        ips: list[str] = []
        ip_items = _ps_json(
            "Get-NetIPAddress -InterfaceAlias '" + name + "' -ErrorAction SilentlyContinue"
            " | Where-Object { $_.AddressFamily -eq 'IPv4'"
            " -or ($_.AddressFamily -eq 'IPv6' -and $_.PrefixOrigin -ne 'WellKnown') }"
            " | Select-Object IPAddress, PrefixLength | ConvertTo-Json -Depth 2"
        )
        for ip in ip_items:
            addr = ip.get("IPAddress", "")
            if addr:
                ips.append(f"{addr}/{ip.get('PrefixLength', '')}")
        result.append({
            "name": name,
            "status": item.get("Status", ""),
            "description": item.get("InterfaceDescription", ""),
            "mac": item.get("MacAddress", ""),
            "ips": ips,
        })
    return result


def _gateways() -> list[str]:
    items = _ps_json(
        "Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue"
        " | Select-Object NextHop, InterfaceAlias | ConvertTo-Json -Depth 2"
    )
    return [
        "{} ({})".format(i.get("NextHop", ""), i.get("InterfaceAlias", ""))
        for i in items
        if i.get("NextHop") and i["NextHop"] not in ("0.0.0.0", "::")
    ]


def _dns_servers() -> list[str]:
    items = _ps_json(
        "Get-DnsClientServerAddress -AddressFamily IPv4"
        " | Where-Object { $_.ServerAddresses.Count -gt 0 }"
        " | Select-Object InterfaceAlias, ServerAddresses | ConvertTo-Json -Depth 3"
    )
    result = []
    for item in items:
        alias = item.get("InterfaceAlias", "")
        addrs = item.get("ServerAddresses", [])
        if isinstance(addrs, str):
            addrs = [addrs]
        for addr in addrs:
            result.append("{} ({})".format(addr, alias))
    return result


def _system_proxy() -> dict:
    items = _ps_json(
        "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings'"
        " -ErrorAction SilentlyContinue"
        " | Select-Object ProxyEnable, ProxyServer, ProxyOverride | ConvertTo-Json"
    )
    if not items:
        return {}
    item = items[0]
    return {
        "enabled": bool(item.get("ProxyEnable", 0)),
        "server": item.get("ProxyServer") or "",
        "override": item.get("ProxyOverride") or "",
    }


def _winhttp_proxy() -> str:
    raw = _run_cmd(["netsh", "winhttp", "show", "proxy"], timeout=10)
    for line in raw.splitlines():
        line = line.strip()
        if "Proxy Server" in line or "Direct access" in line:
            return line
    return raw.splitlines()[0].strip() if raw else ""


def _vpn_processes() -> list[dict]:
    items = _ps_json(
        "Get-Process | Select-Object Name, Id, Path | ConvertTo-Json -Depth 2"
    )
    seen: set[str] = set()
    found = []
    for item in items:
        raw_name = item.get("Name") or ""
        name_lower = raw_name.lower()
        for proxy_name in PROXY_PROCESS_NAMES:
            if proxy_name in name_lower and name_lower not in seen:
                seen.add(name_lower)
                exe_path = item.get("Path") or ""
                found.append({
                    "name": raw_name,
                    "pid": item.get("Id"),
                    "exe": Path(exe_path).name if exe_path else "",
                })
    return found


def _tun_adapters(adapters: list[dict]) -> list[str]:
    keywords = {"tun", "tap", "wintun", "wireguard", "clash", "mihomo",
                "sing-box", "virtual", "loopback"}
    result = []
    for a in adapters:
        combined = ((a.get("description") or "") + " " + (a.get("name") or "")).lower()
        if any(k in combined for k in keywords):
            result.append("{} ({})".format(a["name"], a.get("description", "")))
    return result


def _listening_ports() -> list[dict]:
    items = _ps_json(
        "Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue"
        " | Select-Object LocalAddress, LocalPort, OwningProcess"
        " | Sort-Object LocalPort | ConvertTo-Json -Depth 2"
    )
    if not items:
        return []

    pids = {i.get("OwningProcess") for i in items if i.get("OwningProcess")}
    pid_to_name: dict[int, str] = {}
    if pids:
        pid_list = ",".join(str(p) for p in pids if p)
        proc_items = _ps_json(
            "Get-Process -Id @({}) -ErrorAction SilentlyContinue"
            " | Select-Object Id, Name | ConvertTo-Json -Depth 2".format(pid_list)
        )
        for p in proc_items:
            pid_to_name[p.get("Id")] = p.get("Name", "")

    seen: set[tuple] = set()
    ports = []
    for item in items:
        addr = item.get("LocalAddress", "")
        port = item.get("LocalPort")
        pid = item.get("OwningProcess")
        if port is None:
            continue
        key = (addr, port)
        if key in seen:
            continue
        seen.add(key)
        ports.append({
            "address": addr,
            "port": port,
            "pid": pid,
            "process": pid_to_name.get(pid, ""),
        })
    return sorted(ports, key=lambda x: x["port"])


def collect_network() -> dict:
    adapters = _adapters()
    return {
        "adapters": adapters,
        "gateways": _gateways(),
        "dns_servers": _dns_servers(),
        "proxy": {
            "system_proxy": _system_proxy(),
            "winhttp_proxy": _winhttp_proxy(),
        },
        "vpn_processes": _vpn_processes(),
        "tun_adapters": _tun_adapters(adapters),
        "listening_ports": _listening_ports(),
    }


# ---------------------------------------------------------------------------
# Services collection
# ---------------------------------------------------------------------------

def _service_image_path(path_name: str) -> str:
    """Extract the executable out of a Win32_Service PathName."""
    raw = (path_name or "").strip()
    if not raw:
        return ""
    if raw.startswith('"'):
        end = raw.find('"', 1)
        return raw[1:end] if end > 0 else raw[1:]
    match = re.match(r"^(.*?\.exe)(?:\s|$)", raw, re.IGNORECASE)
    return match.group(1) if match else raw.split(" ", 1)[0]


def _notable_services() -> list[dict]:
    # Win32_Service reports State/StartMode as strings ("Running", "Auto") and
    # exposes PathName. Get-Service would serialise its enums as bare integers
    # through ConvertTo-Json, which renders as an unreadable "- 4".
    items = _ps_json(
        "Get-CimInstance Win32_Service"
        " | Where-Object { $_.State -eq 'Running' -or $_.StartMode -eq 'Auto' }"
        " | Select-Object Name, DisplayName, State, StartMode, PathName"
        " | ConvertTo-Json -Depth 2"
    )
    windir = (os.environ.get("SystemRoot") or r"C:\Windows").rstrip("\\").lower()
    notable = []
    for item in items:
        name = item.get("Name", "") or ""
        if name in _SYSTEM_SERVICE_NAMES:
            continue
        image = _service_image_path(item.get("PathName", ""))
        # Anything shipped under %SystemRoot% is an OS service, not a hotspot.
        if image and image.lower().startswith(windir + os.sep):
            continue
        notable.append({
            "name": name,
            "display_name": item.get("DisplayName", "") or "",
            "status": item.get("State", "") or "",
            "start_type": item.get("StartMode", "") or "",
            "image_path": image,
        })
    notable.sort(key=lambda svc: svc["name"].lower())
    return notable[:40]


def _docker() -> dict:
    version = _run_cmd(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=15)
    if not version:
        return {"status": "not_available"}
    containers = []
    raw = _run_cmd(["docker", "ps", "--format", "{{json .}}"], timeout=15)
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            c = json.loads(line)
            containers.append({
                "name": c.get("Names", ""),
                "image": c.get("Image", ""),
                "ports": c.get("Ports", ""),
                "status": c.get("Status", ""),
            })
        except json.JSONDecodeError:
            pass
    return {"status": "running", "server_version": version, "running_containers": containers}


def _iis() -> dict:
    raw = _run_ps(
        "if (Get-Module -ListAvailable -Name WebAdministration) {"
        " Import-Module WebAdministration -ErrorAction SilentlyContinue;"
        " Get-WebSite | Select-Object Name, State | ConvertTo-Json -Depth 2"
        " } else { 'not_installed' }"
    )
    if not raw or raw.strip() == "not_installed":
        return {"status": "not_installed"}
    try:
        sites = json.loads(raw)
        if isinstance(sites, dict):
            sites = [sites]
        return {
            "status": "available",
            "sites": [{"name": s.get("Name"), "state": s.get("State")} for s in sites],
        }
    except json.JSONDecodeError:
        return {"status": "available", "sites": []}


def _winrm() -> dict:
    items = _ps_json(
        "Get-CimInstance Win32_Service -Filter \"Name='WinRM'\" -ErrorAction SilentlyContinue"
        " | Select-Object State, StartMode | ConvertTo-Json"
    )
    if not items:
        return {"status": "not_available"}
    item = items[0]
    return {"status": item.get("State", ""), "start_type": item.get("StartMode", "")}


def _startup_items() -> list[dict]:
    items = _ps_json(
        "Get-CimInstance Win32_StartupCommand"
        " | Select-Object Name, Command, Location, User | ConvertTo-Json -Depth 2"
    )
    return [
        {
            "name": i.get("Name", ""),
            "command": i.get("Command", ""),
            "location": i.get("Location", ""),
            "user": i.get("User", ""),
        }
        for i in items
    ]


def _scheduled_tasks() -> list[dict]:
    items = _ps_json(
        "Get-ScheduledTask"
        " | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*'"
        " -and $_.TaskPath -notlike '\\MicrosoftEdgeUpdater\\*'"
        " -and $_.State -ne 'Disabled' }"
        " | Select-Object TaskName, TaskPath, State | ConvertTo-Json -Depth 2"
    )
    return [
        {
            "name": i.get("TaskName", ""),
            "path": i.get("TaskPath", ""),
            "state": i.get("State", ""),
        }
        for i in items
    ]


def collect_services() -> dict:
    return {
        "notable_services": _notable_services(),
        "docker": _docker(),
        "iis": _iis(),
        "winrm": _winrm(),
        "startup_items": _startup_items(),
        "scheduled_tasks": _scheduled_tasks(),
    }


# ---------------------------------------------------------------------------
# Software collection
# ---------------------------------------------------------------------------

def _display_width(text: str) -> int:
    """Terminal cell width of a string (CJK glyphs occupy two cells)."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _header_columns(header: str) -> list[int]:
    """Display-column offsets where each header field starts.

    A field may itself contain single spaces, so tokens are only broken on runs
    of two or more spaces.
    """
    return [
        _display_width(header[: match.start()])
        for match in re.finditer(r"\S(?:[^\s]|\s(?!\s))*", header)
    ]


def _split_by_columns(line: str, columns: list[int]) -> list[str]:
    """Slice a padded table row at the given display-column offsets.

    Indexing by code point would drift on rows containing CJK names, because
    winget pads by display width, not character count.
    """
    bounds: list[int] = []
    target = 0
    width = 0
    for idx, ch in enumerate(line):
        while target < len(columns) and width >= columns[target]:
            bounds.append(idx)
            target += 1
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    while target < len(columns):
        bounds.append(len(line))
        target += 1

    fields = []
    for i, start in enumerate(bounds):
        end = bounds[i + 1] if i + 1 < len(bounds) else len(line)
        fields.append(line[start:end].strip())
    return fields


def _is_winget_noise(package_id: str) -> bool:
    return any(pattern.search(package_id) for pattern in _WINGET_NOISE_PATTERNS)


def _winget_packages() -> list[dict]:
    raw = _run_cmd(
        ["winget", "list", "--source", "winget", "--disable-interactivity"],
        timeout=60,
    )
    if not raw:
        return []

    lines = raw.splitlines()

    # Locale-independent header detection. winget localises its column titles
    # ("Name/Id/Version" in English, "名称/ID/版本" in zh-CN, and so on), so
    # matching the English words drops every row on a non-English host.
    # The dashed rule under the header is not localised, so anchor on that.
    sep_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and set(stripped) <= {"-", "─", "—"}:
            sep_idx = idx
            break
    if sep_idx is None or sep_idx == 0:
        return []

    header = lines[sep_idx - 1]
    # winget pads columns to a fixed display width, so the only reliable split
    # is by column offset. Whitespace splitting corrupts any row whose name
    # contains a double space ("Microsoft Visual C++ 2010  x64 Redistributable").
    columns = _header_columns(header)
    if len(columns) < 2:
        return []

    packages = []
    truncated = False
    for line in lines[sep_idx + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        # winget streams spinner/progress glyphs on some terminals.
        if set(stripped) <= set("-\\|/ ─█░"):
            continue
        fields = _split_by_columns(line, columns)
        name = fields[0] if fields else ""
        pkg_id = fields[1] if len(fields) > 1 else ""
        version = fields[2] if len(fields) > 2 else ""
        if not name or not pkg_id:
            continue
        if _is_winget_noise(pkg_id):
            continue
        if len(packages) >= _WINGET_MAX:
            truncated = True
            break
        packages.append({
            "name": name,
            "id": pkg_id,
            "version": version,
            "source": "winget",
        })
    if truncated:
        # Never let a cap look like a complete inventory.
        packages.append({
            "name": f"(truncated at {_WINGET_MAX} entries)",
            "id": "",
            "version": "",
            "source": "winget",
        })
    return packages


def _scoop_packages() -> list[dict]:
    raw = _run_cmd(["scoop", "list"], timeout=30)
    if not raw:
        return []
    packages = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.lower().startswith(("installed", "name", "---")):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) >= 1:
            packages.append({
                "name": parts[0],
                "version": parts[1] if len(parts) > 1 else "",
                "source": "scoop",
            })
    return packages


def _is_choco_noise(name: str) -> bool:
    if name.lower() in {item.lower() for item in _CHOCO_NOISE_EXACT}:
        return True
    return any(pattern.search(name) for pattern in _CHOCO_NOISE_PATTERNS)


def _choco_packages() -> list[dict]:
    raw = _run_cmd(["choco", "list", "--local-only", "--limit-output"], timeout=30)
    if not raw:
        return []
    packages = []
    for line in raw.splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|")
            name = parts[0]
            if _is_choco_noise(name):
                continue
            packages.append({
                "name": name,
                "version": parts[1] if len(parts) > 1 else "",
                "source": "chocolatey",
            })
    return packages


def _npm_packages() -> list[dict]:
    """Global npm CLI packages, matched to the Linux collector's semantics."""
    root_raw = _run_cmd(["npm", "root", "-g"], timeout=60)
    if not root_raw:
        return []
    root = Path(root_raw.splitlines()[0].strip())
    if not root.is_dir():
        return []

    packages = []
    # Scoped packages live one level deeper (@scope/name/package.json).
    candidates = list(root.glob("*/package.json")) + list(root.glob("@*/*/package.json"))
    for package_json in candidates:
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        name = data.get("name")
        bin_field = data.get("bin", {})
        if isinstance(bin_field, str):
            executables = [name] if name else []
        elif isinstance(bin_field, dict):
            executables = sorted(bin_field.keys())
        else:
            executables = []
        if not name or not executables:
            continue  # libraries without an entry point are not global tools
        packages.append({
            "name": name,
            "version": data.get("version", ""),
            "executables": executables,
            "source": "npm-global",
        })
    return sorted(packages, key=lambda item: item["name"].lower())


def _pip_console_tools() -> list[dict]:
    """Top-level pip packages that expose console scripts."""
    raw = _run_cmd(["python", "-m", "pip", "list", "--not-required", "--format=json"], timeout=90)
    if not raw:
        return []
    try:
        requested = {
            item["name"].lower(): item.get("version", "")
            for item in json.loads(raw)
            if item.get("name")
        }
    except (json.JSONDecodeError, TypeError, KeyError):
        return []

    packages = []
    for dist in metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except (KeyError, TypeError):
            name = None
        if not name or name.lower() not in requested:
            continue
        executables = sorted(
            {ep.name for ep in dist.entry_points if ep.group == "console_scripts" and ep.name}
        )
        if not executables:
            continue
        packages.append({
            "name": name,
            "version": dist.version or requested.get(name.lower(), ""),
            "executables": executables,
            "source": "pip",
        })
    return sorted(packages, key=lambda item: item["name"].lower())


def _uv_tools() -> list[dict]:
    raw = _run_cmd(["uv", "tool", "list"], timeout=30)
    if not raw:
        return []
    packages = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.lower().startswith("no tools"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s+v?(\S+)", line)
        if match:
            name, version = match.groups()
            packages.append({
                "name": name,
                "version": version,
                "executables": [name],
                "source": "uv",
            })
    return packages


def _manual_packages(docs_home: Path) -> list[dict]:
    manual_file = docs_home / "manual-software.txt"
    if not manual_file.exists():
        return []
    packages = []
    for line in manual_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split(None, 2)
            packages.append({
                "name": parts[0],
                "version": parts[1] if len(parts) > 1 else "",
                "notes": parts[2].lstrip("# ") if len(parts) > 2 else "",
                "source": "manual",
            })
    return packages


def collect_software(docs_home: Path) -> dict:
    return {
        "winget": _winget_packages(),
        "scoop": _scoop_packages(),
        "chocolatey": _choco_packages(),
        "npm-global": _npm_packages(),
        "pip": _pip_console_tools(),
        "uv": _uv_tools(),
        "manual": _manual_packages(docs_home),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _render_network(data: dict, hostname: str, updated_at: str) -> str:
    lines: list[str] = []
    lines += ["# Network Hotspots\n", f"- Host: {hostname}", f"- Updated At: {updated_at}"]

    lines += ["\n## Adapters\n"]
    for a in data.get("adapters", []):
        ips = ", ".join(a.get("ips", [])) or "—"
        lines.append(f"- **{a['name']}** `{a.get('status','')}` — {ips}  \n  _{a.get('description','')}_")

    lines += ["\n## Gateways\n"]
    for gw in data.get("gateways", []) or ["—"]:
        lines.append(f"- {gw}")

    lines += ["\n## DNS Servers\n"]
    for dns in data.get("dns_servers", []) or ["—"]:
        lines.append(f"- {dns}")

    proxy = data.get("proxy", {})
    lines += ["\n## Proxy / VPN\n"]
    sp = proxy.get("system_proxy", {})
    if sp:
        state = "**enabled**" if sp.get("enabled") else "disabled"
        server = f" → `{sp['server']}`" if sp.get("server") else ""
        lines.append(f"- System proxy: {state}{server}")
        if sp.get("override"):
            lines.append(f"  - Override: `{sp['override']}`")
    wh = proxy.get("winhttp_proxy", "")
    if wh:
        lines.append(f"- WinHTTP: {wh}")

    vpn_procs = data.get("vpn_processes", [])
    if vpn_procs:
        lines += ["\n### Active VPN / Proxy Processes\n"]
        for p in vpn_procs:
            lines.append(f"- `{p['name']}` PID {p.get('pid','?')} ({p.get('exe','')})")
    else:
        lines.append("- No known VPN/proxy processes detected")

    tun = data.get("tun_adapters", [])
    if tun:
        lines += ["\n### TUN / TAP / Virtual Adapters\n"]
        for t in tun:
            lines.append(f"- {t}")

    lines += ["\n## Listening Ports\n", "| Port | Address | Process | PID |", "|------|---------|---------|-----|"]
    for p in data.get("listening_ports", []):
        lines.append(f"| {p['port']} | {p['address']} | {p.get('process','')} | {p.get('pid','')} |")

    return "\n".join(lines)


def _render_services(data: dict, hostname: str, updated_at: str) -> str:
    lines: list[str] = []
    lines += ["# Service Hotspots\n", f"- Host: {hostname}", f"- Updated At: {updated_at}"]

    docker = data.get("docker", {})
    lines += ["\n## Docker\n"]
    if docker.get("status") == "not_available":
        lines.append("- Not available or not running")
    else:
        lines.append(f"- Server version: `{docker.get('server_version','?')}`")
        containers = docker.get("running_containers", [])
        if containers:
            lines += ["", "| Name | Image | Ports | Status |", "|------|-------|-------|--------|"]
            for c in containers:
                lines.append(f"| {c['name']} | {c['image']} | {c['ports']} | {c['status']} |")
        else:
            lines.append("- No running containers")

    iis = data.get("iis", {})
    lines += ["\n## IIS\n"]
    if iis.get("status") == "not_installed":
        lines.append("- Not installed")
    else:
        for s in iis.get("sites", []):
            lines.append(f"- {s['name']} — {s['state']}")

    winrm = data.get("winrm", {})
    lines += ["\n## WinRM\n"]
    lines.append(f"- Status: {winrm.get('status','?')}, StartType: {winrm.get('start_type','?')}")

    # The list also carries Automatic-but-stopped services, so it is not a
    # "running" list.
    lines += ["\n## Notable Services (Non-System)\n"]
    svcs = data.get("notable_services", [])
    if svcs:
        for svc in svcs:
            start = svc.get("start_type", "")
            suffix = f" (start: {start})" if start else ""
            lines.append(
                f"- `{svc['name']}` {svc['display_name']} — {svc.get('status','?')}{suffix}"
            )
    else:
        lines.append("- None detected outside system defaults")

    startup = data.get("startup_items", [])
    if startup:
        lines += ["\n## Startup Items\n"]
        for s in startup:
            lines.append(f"- **{s['name']}** `{s['command']}` ({s['location']}) [{s['user']}]")

    tasks = data.get("scheduled_tasks", [])
    if tasks:
        lines += ["\n## Scheduled Tasks (Non-Microsoft)\n"]
        for t in tasks:
            lines.append(f"- `{t['path']}{t['name']}` — {t['state']}")

    return "\n".join(lines)


def _render_software(data: dict, hostname: str, updated_at: str) -> str:
    lines: list[str] = []
    lines += ["# Installed Software\n", f"- Host: {hostname}", f"- Updated At: {updated_at}"]

    winget = data.get("winget", [])
    if winget:
        lines += [f"\n## winget ({len(winget)} packages)\n"]
        for p in winget:
            lines.append(f"- {p['name']} `{p.get('id','')}` {p.get('version','')}")

    scoop = data.get("scoop", [])
    if scoop:
        lines += [f"\n## scoop ({len(scoop)} packages)\n"]
        for p in scoop:
            lines.append(f"- {p['name']} {p.get('version','')}")

    choco = data.get("chocolatey", [])
    if choco:
        lines += [f"\n## chocolatey ({len(choco)} packages)\n"]
        for p in choco:
            lines.append(f"- {p['name']} {p.get('version','')}")

    for source, title in (("npm-global", "npm (global)"), ("pip", "pip"), ("uv", "uv tools")):
        items = data.get(source, [])
        if not items:
            continue
        lines += [f"\n## {title} ({len(items)} packages)\n"]
        for p in items:
            execs = ", ".join(p.get("executables", []))
            suffix = f" | executables: {execs}" if execs else ""
            lines.append(f"- {p['name']} {p.get('version','')}{suffix}")

    manual = data.get("manual", [])
    if manual:
        lines += ["\n## Manual Installs\n"]
        for p in manual:
            note = f" — {p['notes']}" if p.get("notes") else ""
            lines.append(f"- {p['name']} {p.get('version','')}{note}")

    return "\n".join(lines)


def _render_index(
    network: dict, services: dict, software: dict,
    hostname: str, updated_at: str, docs_home: Path,
) -> str:
    lines: list[str] = []
    lines += [
        "# Host Ops Summary\n",
        f"- Host: {hostname}",
        f"- Updated At: {updated_at}",
        f"- Docs Home: {docs_home}",
        "\n## Highlights\n",
    ]

    adapters_up = [a for a in network.get("adapters", []) if a.get("status") == "Up"]
    lines.append(f"- Adapters up: {len(adapters_up)}")

    sp = network.get("proxy", {}).get("system_proxy", {})
    if sp.get("enabled"):
        lines.append(f"- System proxy **active**: `{sp.get('server','')}`")
    else:
        lines.append("- System proxy: disabled")

    vpn = network.get("vpn_processes", [])
    if vpn:
        names = ", ".join(p["name"] for p in vpn)
        lines.append(f"- VPN/proxy processes running: {names}")
    else:
        lines.append("- No VPN/proxy processes detected")

    lines.append(f"- Listening ports: {len(network.get('listening_ports', []))}")

    docker = services.get("docker", {})
    if docker.get("status") == "running":
        n = len(docker.get("running_containers", []))
        lines.append(f"- Docker: running, {n} container(s)")

    iis = services.get("iis", {})
    if iis.get("status") != "not_installed":
        lines.append(f"- IIS: {len(iis.get('sites', []))} site(s)")

    sources = ("winget", "scoop", "chocolatey", "npm-global", "pip", "uv", "manual")
    total = sum(len(software.get(source, [])) for source in sources)
    lines.append(f"- Tracked packages: {total} (winget/scoop/choco/npm/pip/uv/manual)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def _meaningful_changes(old: dict, new: dict) -> list[str]:
    changes: list[str] = []

    old_net = old.get("network", {})
    new_net = new.get("network", {})

    if not new_net:
        return changes

    # Proxy state
    old_sp = old_net.get("proxy", {}).get("system_proxy", {})
    new_sp = new_net.get("proxy", {}).get("system_proxy", {})
    if old_sp.get("enabled") != new_sp.get("enabled"):
        state = "enabled" if new_sp.get("enabled") else "disabled"
        changes.append(f"System proxy {state}")
    if old_sp.get("server") != new_sp.get("server") and new_sp.get("server"):
        changes.append(f"System proxy server → {new_sp['server']}")

    # VPN/proxy processes
    old_vpn = {p["name"] for p in old_net.get("vpn_processes", [])}
    new_vpn = {p["name"] for p in new_net.get("vpn_processes", [])}
    for name in sorted(new_vpn - old_vpn):
        changes.append(f"VPN/proxy process started: {name}")
    for name in sorted(old_vpn - new_vpn):
        changes.append(f"VPN/proxy process stopped: {name}")

    # Listening ports
    old_ports = {(p["address"], p["port"]) for p in old_net.get("listening_ports", [])}
    new_ports = {(p["address"], p["port"]) for p in new_net.get("listening_ports", [])}
    for addr, port in sorted(new_ports - old_ports):
        changes.append(f"New listening port: {addr}:{port}")
    for addr, port in sorted(old_ports - new_ports):
        changes.append(f"Removed listening port: {addr}:{port}")

    # Software — skip if this run didn't collect software (focused run)
    old_sw = old.get("software", {})
    new_sw = new.get("software", {})
    if new_sw:
        for source in ("winget", "scoop", "chocolatey", "npm-global", "pip", "uv"):
            old_pkgs = {p["name"]: p.get("version", "") for p in old_sw.get(source, [])}
            new_pkgs = {p["name"]: p.get("version", "") for p in new_sw.get(source, [])}
            for name in sorted(set(new_pkgs) - set(old_pkgs)):
                changes.append(f"[{source}] Installed: {name} {new_pkgs[name]}")
            for name in sorted(set(old_pkgs) - set(new_pkgs)):
                changes.append(f"[{source}] Removed: {name}")
            for name in sorted(set(old_pkgs) & set(new_pkgs)):
                if old_pkgs[name] != new_pkgs[name] and new_pkgs[name]:
                    changes.append(f"[{source}] Updated: {name} {old_pkgs[name]} → {new_pkgs[name]}")

    return changes


# ---------------------------------------------------------------------------
# Doc writing
# ---------------------------------------------------------------------------

def _write_docs(
    state: dict[str, Any],
    docs_home: Path,
    reason: str | None,
    focus: list[str],
) -> dict:
    hostname = _hostname()
    updated_at = _now_iso()
    host_dir = docs_home / "hosts" / hostname
    snap_dir = host_dir / "snapshots"
    host_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)

    network = state.get("network", {})
    services = state.get("services", {})
    software = state.get("software", {})

    snap_file = snap_dir / "latest.json"
    old_snap: dict = {}
    if snap_file.exists():
        try:
            old_snap = json.loads(snap_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    new_snap = {"network": network, "services": services, "software": software}
    changes = _meaningful_changes(old_snap, new_snap)
    if reason:
        changes.insert(0, f"Reason: {reason}")

    (host_dir / "network.md").write_text(
        _render_network(network, hostname, updated_at), encoding="utf-8"
    )
    (host_dir / "services.md").write_text(
        _render_services(services, hostname, updated_at), encoding="utf-8"
    )
    (host_dir / "software.md").write_text(
        _render_software(software, hostname, updated_at), encoding="utf-8"
    )
    (host_dir / "index.md").write_text(
        _render_index(network, services, software, hostname, updated_at, docs_home),
        encoding="utf-8",
    )

    if changes:
        entry = "\n## {}\n\n{}\n".format(
            updated_at, "\n".join(f"- {c}" for c in changes)
        )
        with open(host_dir / "changes.md", "a", encoding="utf-8") as f:
            f.write(entry)

    snap_file.write_text(
        json.dumps(new_snap, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )

    return {
        "hostname": hostname,
        "updated_at": updated_at,
        "docs_home": str(docs_home),
        "host_dir": str(host_dir),
        "changes_recorded": len(changes),
        "changes": changes,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def update_docs(reason: str | None = None, focus: list[str] | None = None) -> dict:
    focus = focus or []
    docs_home = _docs_home()

    state: dict[str, Any] = {}
    state["network"] = collect_network() if (not focus or "network" in focus) else {}
    state["services"] = collect_services() if (not focus or "services" in focus) else {}
    state["software"] = collect_software(docs_home) if (not focus or "software" in focus) else {}

    return _write_docs(state, docs_home, reason, focus)
