# win-ops-doc-maintainer

Maintain low-noise, hotspot-only Windows operations documentation for a single host.

## What it does

Runs read-only inspection of the local Windows machine and writes structured Markdown docs to a shared directory. Emphasises network state (especially VPN/proxy tools like Clash), listening ports, and installed software.

## Key differences from ops-doc-maintainer (Linux)

| Area | Linux version | This version |
|---|---|---|
| Shell | bash | Python + PowerShell subprocess |
| Network | ss, ip, iptables | Get-NetTCPConnection, Get-NetAdapter, netsh |
| Services | systemctl | Get-Service, Win32_StartupCommand |
| Package managers | apt, snap, pip, uv | winget, scoop, chocolatey |
| VPN/Proxy | — | Clash, Mihomo, WireGuard, V2Ray process + TUN adapter detection |
| SQL | PostgreSQL | **Excluded by design** |
| Web server | Nginx | IIS (optional) |

## Requirements

- Python 3.8+
- PowerShell 5.1+ (Windows built-in) or pwsh
- Optional: winget, scoop, choco in PATH for software inventory

## Quick start

```bash
python scripts/update_ops_docs.py
```

Docs are written to `%USERPROFILE%\.win-ops-doc-maintainer-docs\hosts\<hostname>\`.
