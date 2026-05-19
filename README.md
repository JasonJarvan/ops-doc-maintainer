# ops-doc-maintainer

> The host inventory file that AI coding agents can actually keep current.
> Records the hotspots — ports, services, VPN/proxy state, installed CLIs —
> and drops the noise — CPU, RAM, disks. Linux + Windows, one skill.

[中文文档 / Chinese version →](README.zh.md)

---

## Why this exists

If you let an AI coding agent install software, change configs, or spin up
services on a machine, you quickly run into the same problem: a week later
**nobody remembers what was changed, where, or why**. Re-running `lsof`,
`systemctl`, `Get-NetTCPConnection`, etc. on every conversation wastes
tokens and produces inconsistent results.

`ops-doc-maintainer` is a skill that lives next to your agent (Claude Code,
Codex, OpenClaw, …) and keeps a small set of Markdown files describing the
**current hotspots** of one host, plus an **append-only change log**.

It deliberately ignores low-signal inventory (OS version, CPU, RAM, full
disk layout, full process listings). Those things rarely matter and create
review noise.

## What you get

A directory per host under `~/.ops-doc-maintainer-docs/hosts/<hostname>/`
(or the Windows variant) that looks roughly like:

```
hosts/
└── my-workstation/
    ├── index.md          # entry point — links + last-updated timestamps
    ├── network.md        # adapters, listening ports, VPN/proxy summary
    ├── services.md       # docker / nginx (linux) or services / iis (win)
    ├── software.md       # manually installed global CLI tools
    ├── postgres.md       # (linux only) connection guidance, no internals
    └── changes.md        # append-only meaningful changes
```

Excerpt of `network.md` after an agent ran `--reason "Configured Clash proxy"`:

```markdown
## Listening ports

| Proto | Local | PID | Process |
|---|---|---|---|
| TCP  | 0.0.0.0:7890 | 18412 | clash-windows.exe |
| TCP  | 0.0.0.0:7891 | 18412 | clash-windows.exe |
| TCP  | 127.0.0.1:9090 | 18412 | clash-windows.exe |

## Proxy state

- System proxy: `127.0.0.1:7890` (HTTP + HTTPS)
- TUN adapter: `Mihomo` (10.0.0.1/24)
```

And `changes.md` gets a single line appended:

```markdown
- 2026-05-19 14:32 — Configured Clash proxy (network)
```

That's the whole product.

## Install

### As a Claude Code skill

Drop the repo (or a clone) into your Claude Code skills directory:

```bash
git clone https://github.com/JasonJarvan/ops-doc-maintainer.git \
  ~/.claude/skills/ops-doc-maintainer
```

The `SKILL.md` description includes platform-detection triggers, so the
agent will pick it up automatically when you ask it to update host docs.

### As a Codex skill

Place the folder under your `agents/` or skills directory and reference
`agents/<platform>/openai.yaml`.

### Standalone (no agent)

Just run the dispatcher directly:

```bash
git clone https://github.com/JasonJarvan/ops-doc-maintainer.git
cd ops-doc-maintainer
python3 scripts/update_ops_docs.py
```

The dispatcher auto-detects Linux/macOS/Windows and delegates to the right
subtree.

## Platform coverage

| Area              | Linux                                 | Windows                                                       |
|-------------------|---------------------------------------|---------------------------------------------------------------|
| Shell             | bash                                  | Python + PowerShell subprocess                                |
| Network           | `ss`, `ip`, `iptables`                | `Get-NetTCPConnection`, `Get-NetAdapter`, `netsh`             |
| Services          | `systemctl`                           | `Get-Service`, `Win32_StartupCommand`, Scheduled Tasks        |
| Package managers  | `apt`, `snap`, `pip`, `uv`            | `winget`, `scoop`, `chocolatey`                               |
| VPN / Proxy       | —                                     | Clash, Mihomo, WireGuard, V2Ray process + TUN adapter detect  |
| Container         | Docker                                | Docker Desktop                                                |
| Web server        | Nginx                                 | IIS (optional)                                                |
| Remote shell      | SSH                                   | WinRM                                                         |
| SQL               | PostgreSQL (connection guidance only) | **Excluded by design** (SQL Server is out of scope)           |

## How it works

1. `scripts/update_ops_docs.py` is the cross-platform entry point. It
   calls `platform.system()` and dispatches to either
   `scripts/linux/update_ops_docs.py` or `scripts/windows/update_ops_docs.py`.
2. The platform updater runs **read-only** collectors per domain
   (network, services, software, …), each emitting structured data.
3. Domains are merged, noise-filtered against `watchlist.txt` /
   `ignorelist.txt` / `manual-software.txt` (in the docs home), and
   written to the current-state Markdown files.
4. Any **meaningful** delta from the previous run is appended to
   `changes.md` with a timestamp and the operator-supplied `--reason`.

### Common invocations

```bash
# Full refresh
python3 scripts/update_ops_docs.py

# Post-install, narrow scan
python3 scripts/update_ops_docs.py --reason "Installed PowerToys" --focus software

# Network/proxy change
python3 scripts/update_ops_docs.py --reason "Configured Clash proxy" --focus network
```

Valid `--focus` values:

- Linux: `network`, `services`, `software`, `postgresql`
- Windows: `network`, `services`, `software`

## Requirements

- Python 3.8+
- Linux: bash and standard core utils
- Windows: PowerShell 5.1+ (built-in) or pwsh; optional `winget` /
  `scoop` / `choco` in `PATH` for full software inventory

## Boundaries (read this before contributing)

- **Read-only.** Collectors never write to system config or the registry.
- **No secrets.** Connection strings, proxy credentials, private keys, and
  similar are masked or omitted, never stored verbatim.
- **Missing tool = partial data, not a crash.** A host without `winget`
  still produces useful docs.
- **No live database content.** PostgreSQL/SQL Server inventory of users,
  tables, or connections is explicitly out of scope.

See `references/<platform>/safety-and-boundaries.md` for the per-platform
detail.

## Contributing

This skill is intentionally small. Good places to extend:

- Additional VPN/proxy clients (Linux side has none yet).
- A macOS subtree (currently macOS shares the Linux path; some collectors
  silently degrade).
- More agent runtime adapters under `adapters/<platform>/`.

Issues and PRs welcome. If your change adds collectors, please update the
corresponding `references/<platform>/collection-rules.md` so the scope
boundary stays explicit.

## License

MIT — see `LICENSE` (or use under MIT until a `LICENSE` file is added).

## Related

- Used as a git submodule inside [`awesome_agent_tools`](https://github.com/JasonJarvan/awesome_agent_tools).
- Sister skill: `skill-orchestrator` (decides whether a new skill is even needed before you build it).
