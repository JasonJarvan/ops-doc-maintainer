# Collection Rules

Collect only high-signal operational data.

Default sections:

- **network hotspots** (highest priority)
  - all network adapters with status and IP addresses
  - default gateways
  - DNS servers per interface
  - system proxy settings (registry + WinHTTP)
  - VPN/proxy process detection: Clash, Mihomo, WireGuard, V2Ray, Xray, Trojan, ShadowSocks, Netch, and similar
  - TUN/TAP/virtual adapter detection
  - listening TCP ports (non-ephemeral)
- Windows Services (non-system, non-Microsoft, running or auto-start)
- Docker Desktop summary
- IIS status (if installed)
- WinRM status
- user-created startup items
- user-created scheduled tasks (non-Microsoft path)
- manually installed global executable tools (winget / scoop / chocolatey / manual list)

Do not collect:

- OS version, CPU, memory, disks, or mounts
- full process listings
- full package inventories (cap winget at 100 entries)
- full log files or event viewer output
- full config file bodies
- secrets, tokens, private keys, or passwords
- proxy credentials or VPN key material
- SQL Server or any database internals
- Microsoft-signed or built-in Windows services

Noise reduction:

- current-state docs must overwrite previous current state
- `changes.md` only records meaningful changes
- ignore ordering-only differences
- ignore unchanged status checks
- prefer summaries over raw command output
- cap notable services list at 30 entries
