#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from string import Template
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
DEFAULT_DOCS_HOME = Path.home() / ".ops-doc-maintainer-docs"
POSTGRESQL_COMPOSE_PATH = Path("/home/shenzhou/Codes/Infra/postgresql/docker-compose.yml")
BIN_DIRS = {
    "/bin",
    "/sbin",
    "/usr/bin",
    "/usr/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def docs_home() -> Path:
    return Path(os.environ.get("OPS_DOCS_HOME", str(DEFAULT_DOCS_HOME))).expanduser()


def host_name() -> str:
    return socket.gethostname().split(".")[0]


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=check,
    )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def bootstrap_docs_home() -> None:
    home = docs_home()
    home.mkdir(parents=True, exist_ok=True)
    for name in ("watchlist.txt", "ignorelist.txt", "manual-software.txt"):
        target = home / name
        template = TEMPLATES / name
        if not target.exists() and template.exists():
            target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")


def parse_watch_or_ignore(path: Path) -> dict[str, set[str]]:
    items: dict[str, set[str]] = defaultdict(set)
    for line in load_lines(path):
        if ":" not in line:
            continue
        kind, value = line.split(":", 1)
        items[kind.strip()].add(value.strip())
    return items


def parse_manual_software(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in load_lines(path):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        name, version, executables = parts[:3]
        notes = parts[3] if len(parts) > 3 else ""
        rows.append(
            {
                "name": name,
                "source": "manual-binary",
                "version": version or "unknown",
                "executables": sorted(
                    [item.strip() for item in executables.split(",") if item.strip()]
                ),
                "notes": notes,
            }
        )
    return rows


def normalize_records(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for record in records:
        record = json.loads(json.dumps(record, sort_keys=True))
        marker = json.dumps(record, sort_keys=True)
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(record)
    return sorted(normalized, key=lambda item: json.dumps(item.get(key, item), sort_keys=True))


def collect_network() -> dict[str, Any]:
    ip_output = run(["hostname", "-I"]).stdout.strip()
    ips = [ip for ip in ip_output.split() if ip]
    default_route = run(["ip", "route", "show", "default"]).stdout.strip().splitlines()
    dns_servers = []
    resolv = Path("/etc/resolv.conf")
    if resolv.exists():
        for line in resolv.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("nameserver "):
                dns_servers.append(line.split(None, 1)[1])

    listening_ports: list[dict[str, Any]] = []
    if command_exists("ss"):
        ss_result = run(["ss", "-ltnupH"])
        for line in ss_result.stdout.splitlines():
            parts = re.split(r"\s+", line.strip(), maxsplit=6)
            if len(parts) < 5:
                continue
            proto = parts[0]
            local = parts[4]
            process = parts[6] if len(parts) > 6 else ""
            host, port = split_host_port(local)
            listening_ports.append(
                {
                    "proto": proto,
                    "address": host,
                    "port": port,
                    "process": clean_process(process),
                }
            )

    firewall = {"tool": "none", "summary": []}
    if command_exists("ufw"):
        status = run(["ufw", "status"])
        if status.returncode == 0:
            firewall = {"tool": "ufw", "summary": status.stdout.strip().splitlines()[:12]}
    elif command_exists("nft"):
        result = run(["nft", "list", "ruleset"])
        if result.returncode == 0:
            firewall = {
                "tool": "nft",
                "summary": [line for line in result.stdout.splitlines()[:12] if line.strip()],
            }

    data = {
        "updated_at": now_iso(),
        "hostname": host_name(),
        "primary_ips": sorted(ips),
        "default_route": default_route[0] if default_route else "",
        "dns_servers": sorted(dict.fromkeys(dns_servers)),
        "listening_ports": normalize_records(listening_ports, "port"),
        "firewall": firewall,
    }
    return data


def split_host_port(value: str) -> tuple[str, str]:
    value = value.strip()
    if value.startswith("[") and "]:" in value:
        host, port = value.rsplit("]:", 1)
        return host[1:], port
    if ":" in value:
        host, port = value.rsplit(":", 1)
        return host, port
    return value, ""


def clean_process(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("users:((", "").replace("))", "")
    cleaned = cleaned.replace('"', "")
    return cleaned


def systemd_status(unit: str) -> dict[str, str]:
    if not command_exists("systemctl"):
        return {"unit": unit, "status": "unknown"}
    result = run(["systemctl", "is-active", unit])
    status = result.stdout.strip() or result.stderr.strip() or "unknown"
    return {"unit": unit, "status": status}


def collect_docker() -> dict[str, Any]:
    status = systemd_status("docker")
    containers: list[dict[str, Any]] = []
    if command_exists("docker"):
        result = run(
            [
                "docker",
                "ps",
                "--format",
                "{{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}\t{{.RunningFor}}",
            ]
        )
        for line in result.stdout.splitlines():
            name, image, ports, status_text, running_for = (line.split("\t") + ["", "", "", "", ""])[:5]
            containers.append(
                {
                    "name": name,
                    "image": image,
                    "ports": ports,
                    "status": status_text,
                    "running_for": running_for,
                }
            )
    return {
        "status": status["status"],
        "containers": normalize_records(containers, "name"),
    }


def nginx_config_summary() -> dict[str, Any]:
    config_paths = []
    if Path("/etc/nginx/nginx.conf").exists():
        config_paths.append("/etc/nginx/nginx.conf")
    enabled = Path("/etc/nginx/sites-enabled")
    if enabled.exists():
        for path in sorted(enabled.iterdir()):
            if path.is_file() or path.is_symlink():
                config_paths.append(str(path))

    listens: list[str] = []
    server_names: list[str] = []
    upstreams: list[str] = []
    certificates: list[str] = []
    for path_str in config_paths:
        path = Path(path_str)
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("listen "):
                listens.append(line.removeprefix("listen ").rstrip(";"))
            elif line.startswith("server_name "):
                server_names.extend(
                    item for item in line.removeprefix("server_name ").rstrip(";").split() if item
                )
            elif line.startswith("upstream "):
                upstreams.append(line.removeprefix("upstream ").split("{", 1)[0].strip())
            elif line.startswith("ssl_certificate "):
                certificates.append(line.removeprefix("ssl_certificate ").rstrip(";"))

    test_summary = ""
    if command_exists("nginx"):
        result = run(["nginx", "-t"])
        output = (result.stderr or result.stdout).strip().splitlines()
        test_summary = output[-1] if output else ""

    status = systemd_status("nginx")
    return {
        "status": status["status"],
        "config_paths": sorted(dict.fromkeys(config_paths)),
        "listens": sorted(dict.fromkeys(listens)),
        "server_names": sorted(dict.fromkeys(server_names)),
        "upstreams": sorted(dict.fromkeys(upstreams)),
        "certificate_paths": sorted(dict.fromkeys(certificates)),
        "test_summary": test_summary,
    }


def ssh_summary() -> dict[str, Any]:
    config_paths = []
    base = Path("/etc/ssh/sshd_config")
    if base.exists():
        config_paths.append(str(base))
    conf_d = Path("/etc/ssh/sshd_config.d")
    if conf_d.exists():
        for path in sorted(conf_d.iterdir()):
            if path.is_file():
                config_paths.append(str(path))

    settings = {
        "Port": [],
        "ListenAddress": [],
        "PermitRootLogin": [],
        "PasswordAuthentication": [],
        "PubkeyAuthentication": [],
    }
    for path_str in config_paths:
        try:
            content = Path(path_str).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in content.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            key, value = parts
            if key in settings:
                settings[key].append(value.strip())

    status = systemd_status("ssh")
    if status["status"] == "unknown":
        status = systemd_status("sshd")

    return {
        "status": status["status"],
        "config_paths": sorted(dict.fromkeys(config_paths)),
        "ports": sorted(dict.fromkeys(settings["Port"])),
        "listen_addresses": sorted(dict.fromkeys(settings["ListenAddress"])),
        "permit_root_login": sorted(dict.fromkeys(settings["PermitRootLogin"])),
        "password_authentication": sorted(dict.fromkeys(settings["PasswordAuthentication"])),
        "pubkey_authentication": sorted(dict.fromkeys(settings["PubkeyAuthentication"])),
    }


def collect_services() -> dict[str, Any]:
    return {
        "updated_at": now_iso(),
        "hostname": host_name(),
        "docker": collect_docker(),
        "nginx": nginx_config_summary(),
        "ssh": ssh_summary(),
    }


def postgresql_units() -> list[str]:
    if not command_exists("systemctl"):
        return []
    result = run(["systemctl", "list-units", "--type=service", "--all", "postgresql*.service"])
    units = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].startswith("postgresql"):
            units.append(parts[0])
    return sorted(dict.fromkeys(units))


def psql_query(sql: str) -> list[str]:
    if not command_exists("psql"):
        return []
    cmd = ["psql", "-Atqc", sql, "postgres"]
    result = run(cmd)
    if result.returncode != 0:
        cmd = ["psql", "-Atqc", sql]
        result = run(cmd)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def postgresql_config_paths() -> list[str]:
    paths = []
    if POSTGRESQL_COMPOSE_PATH.exists():
        paths.append(str(POSTGRESQL_COMPOSE_PATH))
    for candidate in [
        Path("/etc/postgresql"),
        Path("/var/lib/postgresql"),
    ]:
        if candidate.exists():
            for path in candidate.rglob("postgresql.conf"):
                paths.append(str(path))
            for path in candidate.rglob("pg_hba.conf"):
                paths.append(str(path))
    return sorted(dict.fromkeys(paths))


def parse_postgresql_compose() -> dict[str, Any]:
    data: dict[str, Any] = {}
    if not POSTGRESQL_COMPOSE_PATH.exists():
        return data
    try:
        content = POSTGRESQL_COMPOSE_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return data

    port_match = re.search(r'^\s*-\s*"?(?P<host>\d+):(?P<container>\d+)"?\s*$', content, re.MULTILINE)
    user_match = re.search(r"^\s*POSTGRES_USER:\s*(?P<value>.+?)\s*$", content, re.MULTILINE)
    db_match = re.search(r"^\s*POSTGRES_DB:\s*(?P<value>.+?)\s*$", content, re.MULTILINE)
    service_match = re.search(r"^\s{2}(?P<service>postgresql):\s*$", content, re.MULTILINE)
    container_match = re.search(r"^\s*container_name:\s*(?P<value>.+?)\s*$", content, re.MULTILINE)

    if port_match:
        data["host_port"] = port_match.group("host")
        data["container_port"] = port_match.group("container")
    if user_match:
        data["user"] = user_match.group("value").strip().strip('"').strip("'")
    if db_match:
        data["database"] = db_match.group("value").strip().strip('"').strip("'")
    if service_match:
        data["service_name"] = service_match.group("service")
    if container_match:
        data["container_name"] = container_match.group("value").strip().strip('"').strip("'")
    return data


def collect_postgresql() -> dict[str, Any]:
    units = postgresql_units()
    status = "not-found"
    if units:
        statuses = [systemd_status(unit)["status"] for unit in units]
        status = ", ".join(sorted(dict.fromkeys(statuses)))
    elif command_exists("psql"):
        status = "present"
    compose = parse_postgresql_compose()
    host_port = compose.get("host_port", "5432")
    database = compose.get("database", "postgres")
    user = compose.get("user", "postgres")
    connect_examples = [
        f"psql -h 127.0.0.1 -p {host_port} -U {user} -d {database}",
    ]
    if compose.get("container_name"):
        connect_examples.append(
            f"docker exec -it {compose['container_name']} psql -U {user} -d {database}"
        )

    return {
        "updated_at": now_iso(),
        "hostname": host_name(),
        "status": status,
        "units": units,
        "config_paths": postgresql_config_paths(),
        "connection": {
            "method": "compose" if compose else "unknown",
            "host": "127.0.0.1",
            "host_port": host_port,
            "database": database,
            "user": user,
            "container_name": compose.get("container_name", ""),
            "service_name": compose.get("service_name", ""),
            "examples": connect_examples,
            "password_hint": f"See {POSTGRESQL_COMPOSE_PATH}" if compose else "",
        },
    }


def package_executables(package: str) -> list[str]:
    result = run(["dpkg", "-L", package])
    if result.returncode != 0:
        return []
    executables = []
    for line in result.stdout.splitlines():
        path = Path(line.strip())
        if str(path.parent) in BIN_DIRS and path.is_file() and os.access(path, os.X_OK):
            executables.append(path.name)
    return sorted(dict.fromkeys(executables))


def apt_tools() -> list[dict[str, Any]]:
    if not command_exists("apt-mark") or not command_exists("dpkg-query"):
        return []
    result = run(["apt-mark", "showmanual"])
    rows = []
    for package in [line.strip() for line in result.stdout.splitlines() if line.strip()]:
        meta = run(["dpkg-query", "-W", "-f=${Priority}\t${Essential}", package])
        priority, essential = ((meta.stdout.strip().split("\t") + ["", ""])[:2])
        if essential == "yes":
            continue
        if priority in {"required", "important", "standard"}:
            continue
        executables = package_executables(package)
        if not executables:
            continue
        version = run(["dpkg-query", "-W", f"-f=${{Version}}", package]).stdout.strip() or "unknown"
        rows.append(
            {
                "name": package,
                "source": "apt-manual",
                "version": version,
                "executables": executables,
            }
        )
    return normalize_records(rows, "name")


def snap_tools() -> list[dict[str, Any]]:
    if not command_exists("snap"):
        return []
    skip_names = {"firmware-updater", "snap-store", "snapd-desktop-integration"}
    snap_meta: dict[str, dict[str, str]] = {}
    result = run(["snap", "list"])
    for line in result.stdout.splitlines()[1:]:
        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) >= 2:
            snap_meta[cols[0]] = {
                "version": cols[1],
                "notes": cols[-1] if cols else "",
            }

    aliases = defaultdict(list)
    alias_result = run(["snap", "aliases"])
    for line in alias_result.stdout.splitlines()[1:]:
        cols = re.split(r"\s{2,}", line.strip())
        if len(cols) >= 2 and cols[1] != "-":
            aliases[cols[0]].append(cols[1])

    rows = []
    for name, meta in snap_meta.items():
        version = meta["version"]
        notes = meta["notes"]
        commands = sorted(dict.fromkeys([name] + aliases.get(name, [])))
        if name in skip_names:
            continue
        if notes == "base":
            continue
        if name.startswith("core") or name in {"bare", "snapd", "gtk-common-themes"}:
            if not aliases.get(name):
                continue
        if re.match(r"^(gnome|mesa)-", name):
            continue
        rows.append(
            {
                "name": name,
                "source": "snap",
                "version": version,
                "executables": commands,
            }
        )
    return normalize_records(rows, "name")


def npm_tools() -> list[dict[str, Any]]:
    if not command_exists("npm"):
        return []
    root_result = run(["npm", "root", "-g"])
    if root_result.returncode != 0:
        return []
    root = Path(root_result.stdout.strip())
    rows = []
    if not root.exists():
        return rows
    for package_json in root.glob("*/package.json"):
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name")
        version = data.get("version", "unknown")
        bin_field = data.get("bin", {})
        executables: list[str]
        if isinstance(bin_field, str):
            executables = [name] if name else []
        elif isinstance(bin_field, dict):
            executables = sorted(bin_field.keys())
        else:
            executables = []
        if not name or not executables:
            continue
        rows.append(
            {
                "name": name,
                "source": "npm-global",
                "version": version,
                "executables": executables,
            }
        )
    return normalize_records(rows, "name")


def python_requested_packages() -> tuple[set[str], set[str]]:
    pip_names: set[str] = set()
    conda_names: set[str] = set()

    if command_exists("python3"):
        result = run(["python3", "-m", "pip", "list", "--not-required", "--format=json"])
        if result.returncode == 0:
            try:
                for item in json.loads(result.stdout):
                    name = item.get("name")
                    if name:
                        pip_names.add(name.lower())
            except json.JSONDecodeError:
                pass

    if command_exists("conda"):
        result = run(["conda", "env", "export", "--from-history", "--json"])
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                for dep in data.get("dependencies", []):
                    if isinstance(dep, str):
                        conda_names.add(dep.split("=", 1)[0].strip().lower())
            except json.JSONDecodeError:
                pass
    return pip_names, conda_names


def python_console_tools() -> list[dict[str, Any]]:
    pip_names, conda_names = python_requested_packages()
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        name_key = name.lower()
        installer = (dist.read_text("INSTALLER") or "").strip().lower()
        if name_key in conda_names and installer != "pip":
            source = "conda"
        elif name_key in pip_names:
            source = "python-pip" if installer != "uv" else "uv"
        else:
            continue

        executables = sorted(
            {
                ep.name
                for ep in dist.entry_points
                if ep.group == "console_scripts" and ep.name
            }
        )
        if not executables:
            continue
        key = (source, name)
        buckets[key] = {
            "name": name,
            "source": source,
            "version": dist.version or "unknown",
            "executables": executables,
        }
    return normalize_records(list(buckets.values()), "name")


def uv_tools() -> list[dict[str, Any]]:
    if not command_exists("uv"):
        return []
    result = run(["uv", "tool", "list"])
    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.startswith("No tools"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s+v?([^\s]+)", line)
        if match:
            name, version = match.groups()
            rows.append(
                {
                    "name": name,
                    "source": "uv",
                    "version": version,
                    "executables": [name],
                }
            )
    return normalize_records(rows, "name")


def collect_software() -> dict[str, Any]:
    manual_rows = parse_manual_software(docs_home() / "manual-software.txt")
    all_rows = (
        apt_tools()
        + snap_tools()
        + npm_tools()
        + python_console_tools()
        + uv_tools()
        + manual_rows
    )
    return {
        "updated_at": now_iso(),
        "hostname": host_name(),
        "tools": normalize_records(all_rows, "name"),
    }


def normalize_state() -> dict[str, Any]:
    bootstrap_docs_home()
    data = {
        "hostname": host_name(),
        "collected_at": now_iso(),
        "network": collect_network(),
        "services": collect_services(),
        "postgresql": collect_postgresql(),
        "software": collect_software(),
    }
    return apply_filters(data)


def apply_filters(data: dict[str, Any]) -> dict[str, Any]:
    docs = docs_home()
    watch = parse_watch_or_ignore(docs / "watchlist.txt")
    ignore = parse_watch_or_ignore(docs / "ignorelist.txt")

    ports = []
    for item in data["network"]["listening_ports"]:
        port = str(item.get("port", ""))
        addr = item.get("address", "")
        process = item.get("process", "")
        if port in ignore.get("port", set()):
            continue
        if addr in {"127.0.0.1", "::1"} and port not in watch.get("port", set()):
            continue
        if addr.startswith("127.0.0.") and port not in watch.get("port", set()):
            continue
        ports.append(item)
    data["network"]["listening_ports"] = normalize_records(ports, "port")

    software_rows = []
    for item in data["software"]["tools"]:
        name = item["name"]
        if name in ignore.get("software", set()):
            continue
        software_rows.append(item)
    data["software"]["tools"] = normalize_records(software_rows, "name")

    containers = []
    for item in data["services"]["docker"]["containers"]:
        if item["name"] in ignore.get("container", set()):
            continue
        containers.append(item)
    data["services"]["docker"]["containers"] = normalize_records(containers, "name")

    for service_name in ("docker", "nginx", "ssh"):
        if service_name in ignore.get("service", set()):
            data["services"][service_name]["ignored"] = True
    if "postgresql" in ignore.get("service", set()):
        data["postgresql"]["ignored"] = True
    if data["postgresql"]["status"] == "not-found":
        for item in data["services"]["docker"]["containers"]:
            image = item.get("image", "").lower()
            name = item.get("name", "").lower()
            if "postgres" in image or "postgres" in name:
                data["postgresql"]["status"] = "container-only"
                break
    return data


def json_for_section(section: str) -> dict[str, Any]:
    if section == "network":
        return collect_network()
    if section == "services":
        return collect_services()
    if section == "postgresql":
        return collect_postgresql()
    if section == "software":
        bootstrap_docs_home()
        return collect_software()
    raise ValueError(f"Unknown section: {section}")


def render_markdown(data: dict[str, Any]) -> dict[str, str]:
    host = data["hostname"]
    updated_at = data["collected_at"]
    home = str(docs_home())

    highlights = [
        f"- Listening ports tracked: {len(data['network']['listening_ports'])}",
        f"- Docker containers running: {len(data['services']['docker']['containers'])}",
        f"- Manual global tools tracked: {len(data['software']['tools'])}",
        f"- PostgreSQL connection method: {data['postgresql']['connection']['method']}",
    ]

    network_lines = [
        "## Identity",
        f"- Primary IPs: {', '.join(data['network']['primary_ips']) or 'none'}",
        f"- Default Route: {data['network']['default_route'] or 'unknown'}",
        f"- DNS: {', '.join(data['network']['dns_servers']) or 'none'}",
        "",
        "## Listening Ports",
    ]
    if data["network"]["listening_ports"]:
        for item in data["network"]["listening_ports"]:
            network_lines.append(
                f"- {item['proto']} {item['address']}:{item['port']} {item['process']}".rstrip()
            )
    else:
        network_lines.append("- none")
    network_lines.extend(["", "## Firewall", f"- Tool: {data['network']['firewall']['tool']}"])
    for line in data["network"]["firewall"]["summary"]:
        network_lines.append(f"- {line}")

    services_lines = ["## Docker", f"- Status: {data['services']['docker']['status']}"]
    if data["services"]["docker"]["containers"]:
        for item in data["services"]["docker"]["containers"]:
            services_lines.append(
                f"- {item['name']}: {item['image']} | {item['ports'] or 'no published ports'} | {item['status']}"
            )
    else:
        services_lines.append("- No running containers")

    services_lines.extend(
        [
            "",
            "## Nginx",
            f"- Status: {data['services']['nginx']['status']}",
            f"- Config Paths: {', '.join(data['services']['nginx']['config_paths']) or 'none'}",
            f"- Listen: {', '.join(data['services']['nginx']['listens']) or 'none'}",
            f"- Server Names: {', '.join(data['services']['nginx']['server_names']) or 'none'}",
            f"- Upstreams: {', '.join(data['services']['nginx']['upstreams']) or 'none'}",
            f"- Cert Paths: {', '.join(data['services']['nginx']['certificate_paths']) or 'none'}",
            f"- Config Check: {data['services']['nginx']['test_summary'] or 'not available'}",
            "",
            "## SSH",
            f"- Status: {data['services']['ssh']['status']}",
            f"- Config Paths: {', '.join(data['services']['ssh']['config_paths']) or 'none'}",
            f"- Ports: {', '.join(data['services']['ssh']['ports']) or 'default'}",
            f"- Listen Addresses: {', '.join(data['services']['ssh']['listen_addresses']) or 'default'}",
            f"- PermitRootLogin: {', '.join(data['services']['ssh']['permit_root_login']) or 'default'}",
            f"- PasswordAuthentication: {', '.join(data['services']['ssh']['password_authentication']) or 'default'}",
            f"- PubkeyAuthentication: {', '.join(data['services']['ssh']['pubkey_authentication']) or 'default'}",
            "",
            "## PostgreSQL",
            f"- Status: {data['postgresql']['status']}",
            f"- Units: {', '.join(data['postgresql']['units']) or 'none'}",
            f"- Config Paths: {', '.join(data['postgresql']['config_paths']) or 'none'}",
            f"- Connection Method: {data['postgresql']['connection']['method']}",
            f"- Host: {data['postgresql']['connection']['host']}",
            f"- Host Port: {data['postgresql']['connection']['host_port']}",
            f"- User: {data['postgresql']['connection']['user']}",
            f"- Default Database: {data['postgresql']['connection']['database']}",
            f"- Container Name: {data['postgresql']['connection']['container_name'] or 'unknown'}",
            f"- Service Name: {data['postgresql']['connection']['service_name'] or 'unknown'}",
            f"- Password Hint: {data['postgresql']['connection']['password_hint'] or 'not available'}",
            "- Connection Examples:",
        ]
    )
    for item in data["postgresql"]["connection"]["examples"]:
        services_lines.append(f"  - {item}")

    software_lines = []
    software_items = sorted(data["software"]["tools"], key=lambda item: (item["source"], item["name"].lower()))
    if software_items:
        current_source = None
        for item in software_items:
            if item["source"] != current_source:
                current_source = item["source"]
                software_lines.extend(["", f"## {current_source}"])
            software_lines.append(
                f"- {item['name']} {item['version']} | executables: {', '.join(item['executables'])}"
                + (f" | {item['notes']}" if item.get("notes") else "")
            )
    else:
        software_lines.append("- none")

    return {
        "index.md": fill_template(
            "host-index.md",
            hostname=host,
            updated_at=updated_at,
            docs_home=home,
            highlights="\n".join(highlights),
        ),
        "network.md": fill_template(
            "network.md",
            hostname=host,
            updated_at=updated_at,
            content="\n".join(network_lines),
        ),
        "services.md": fill_template(
            "services.md",
            hostname=host,
            updated_at=updated_at,
            content="\n".join(services_lines),
        ),
        "software.md": fill_template(
            "software.md",
            hostname=host,
            updated_at=updated_at,
            content="\n".join(software_lines).lstrip(),
        ),
    }


def fill_template(name: str, **kwargs: str) -> str:
    template = Template((TEMPLATES / name).read_text(encoding="utf-8"))
    return template.safe_substitute(**kwargs).rstrip() + "\n"


def stable_view(data: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(data, sort_keys=True))


def load_previous_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def meaningful_changes(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    if not previous:
        return ["Initialized ops documentation."]

    changes: list[str] = []
    prev_ports = {(item["proto"], item["address"], item["port"]) for item in previous["network"]["listening_ports"]}
    curr_ports = {(item["proto"], item["address"], item["port"]) for item in current["network"]["listening_ports"]}
    added_ports = sorted(curr_ports - prev_ports)
    removed_ports = sorted(prev_ports - curr_ports)
    for proto, address, port in added_ports:
        changes.append(f"Listening port added: {proto} {address}:{port}")
    for proto, address, port in removed_ports:
        changes.append(f"Listening port removed: {proto} {address}:{port}")

    for service in ("docker", "nginx", "ssh"):
        prev_status = previous["services"][service]["status"]
        curr_status = current["services"][service]["status"]
        if prev_status != curr_status:
            changes.append(f"{service} status changed: {prev_status} -> {curr_status}")

    prev_pg_status = previous["postgresql"]["status"]
    curr_pg_status = current["postgresql"]["status"]
    if prev_pg_status != curr_pg_status:
        changes.append(f"postgresql status changed: {prev_pg_status} -> {curr_pg_status}")

    prev_tools = {item["name"]: item for item in previous["software"]["tools"]}
    curr_tools = {item["name"]: item for item in current["software"]["tools"]}
    for name in sorted(curr_tools.keys() - prev_tools.keys()):
        changes.append(f"Software tool added: {name} ({curr_tools[name]['source']})")
    for name in sorted(prev_tools.keys() - curr_tools.keys()):
        changes.append(f"Software tool removed: {name} ({prev_tools[name]['source']})")
    for name in sorted(curr_tools.keys() & prev_tools.keys()):
        if curr_tools[name]["version"] != prev_tools[name]["version"]:
            changes.append(
                f"Software tool version changed: {name} {prev_tools[name]['version']} -> {curr_tools[name]['version']}"
            )

    prev_containers = {item["name"]: item for item in previous["services"]["docker"]["containers"]}
    curr_containers = {item["name"]: item for item in current["services"]["docker"]["containers"]}
    for name in sorted(curr_containers.keys() - prev_containers.keys()):
        changes.append(f"Docker container started: {name}")
    for name in sorted(prev_containers.keys() - curr_containers.keys()):
        changes.append(f"Docker container stopped: {name}")

    prev_conn = previous["postgresql"].get("connection", {})
    curr_conn = current["postgresql"].get("connection", {})
    for field in ("host", "host_port", "user", "database", "container_name", "service_name", "method"):
        if prev_conn.get(field) != curr_conn.get(field):
            changes.append(
                f"PostgreSQL connection {field} changed: {prev_conn.get(field, 'unknown')} -> {curr_conn.get(field, 'unknown')}"
            )

    return changes


def write_changes(path: Path, hostname: str, timestamp: str, changes: list[str], reason: str | None) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    body = existing.strip()
    if not body:
        body = fill_template("changes.md", hostname=hostname, content="").strip()
    entry_lines = [f"## {timestamp}"]
    if reason:
        entry_lines.append(f"- Reason: {reason}")
    for change in changes:
        entry_lines.append(f"- {change}")
    updated = body.rstrip() + "\n\n" + "\n".join(entry_lines) + "\n"
    path.write_text(updated, encoding="utf-8")


def update_docs(reason: str | None = None, focus: list[str] | None = None) -> dict[str, Any]:
    del focus
    bootstrap_docs_home()
    state = stable_view(normalize_state())
    host_dir = docs_home() / "hosts" / state["hostname"]
    snapshot_dir = host_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    previous = load_previous_snapshot(snapshot_dir / "latest.json")
    docs = render_markdown(state)
    for name, content in docs.items():
        (host_dir / name).write_text(content, encoding="utf-8")
    changes = meaningful_changes(previous, state)
    if changes:
        write_changes(host_dir / "changes.md", state["hostname"], state["collected_at"], changes, reason)
    elif not (host_dir / "changes.md").exists():
        (host_dir / "changes.md").write_text(
            fill_template("changes.md", hostname=state["hostname"], content=""), encoding="utf-8"
        )
    (snapshot_dir / "latest.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "hostname": state["hostname"],
        "docs_home": str(docs_home()),
        "host_dir": str(host_dir),
        "changes_written": len(changes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")

    collect = sub.add_parser("collect")
    collect.add_argument("section", choices=["network", "services", "postgresql", "software"])

    parser.add_argument("--reason", default=None)
    parser.add_argument("--focus", action="append", default=[])

    args = parser.parse_args()
    if args.command == "collect":
        print(json.dumps(json_for_section(args.section), indent=2, sort_keys=True))
        return 0

    result = update_docs(reason=args.reason, focus=args.focus)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
