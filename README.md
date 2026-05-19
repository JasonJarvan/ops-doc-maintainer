# ops-doc-maintainer

Cross-platform ops documentation skill for Codex, Claude Code, and OpenClaw. Auto-detects Linux vs Windows on every invocation.

- Shared docs home (Linux): `$OPS_DOCS_HOME` else `~/.ops-doc-maintainer-docs/`
- Shared docs home (Windows): `$WIN_OPS_DOCS_HOME` or `$OPS_DOCS_HOME` else `~/.win-ops-doc-maintainer-docs/`
- Primary use cases:
  - build a hotspot-only ops inventory for a host
  - refresh docs after software install, upgrade, or config changes
  - maintain low-noise current-state docs and meaningful change history

## Quick start

```bash
python3 scripts/update_ops_docs.py
```

The dispatcher picks the platform implementation under `scripts/linux/` or `scripts/windows/` automatically.

## Platform coverage

| Area | Linux | Windows |
|---|---|---|
| Shell | bash | Python + PowerShell subprocess |
| Network | `ss`, `ip`, `iptables` | `Get-NetTCPConnection`, `Get-NetAdapter`, `netsh` |
| Services | `systemctl` | `Get-Service`, `Win32_StartupCommand` |
| Package managers | `apt`, `snap`, `pip`, `uv` | `winget`, `scoop`, `chocolatey` |
| VPN / Proxy | — | Clash, Mihomo, WireGuard, V2Ray process + TUN adapter detection |
| SQL | PostgreSQL (connection only) | **Excluded by design** |
| Web server | Nginx | IIS (optional) |

## Requirements

- Python 3.8+
- Linux: bash, standard core utils
- Windows: PowerShell 5.1+ (built-in) or pwsh; optional `winget` / `scoop` / `choco` in PATH

See `SKILL.md` for the full workflow and `references/<platform>/` for scope and rules.
