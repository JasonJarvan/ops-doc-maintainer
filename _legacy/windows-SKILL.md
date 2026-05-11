---
name: win-ops-doc-maintainer
description: Maintain hotspot-only Windows operations documentation for a host. Use when you need to inventory network adapters, VPN/proxy state (Clash, WireGuard, etc.), listening ports, Windows Services, Docker, IIS, WinRM, or manually installed global CLI tools, and when another agent has just installed or changed software and the shared ops docs must be updated.
---

# Win Ops Doc Maintainer

Keep this skill portable. The core workflow must stay compatible with Codex, Claude Code, and OpenClaw.

## What This Skill Maintains

This skill updates shared host docs in:

- `$WIN_OPS_DOCS_HOME` or `$OPS_DOCS_HOME` when set
- otherwise `~/.win-ops-doc-maintainer-docs/`

It records only hotspot information:

- network adapters, IPs, gateways, DNS
- VPN / proxy state: Clash, Mihomo, WireGuard, V2Ray, and similar processes; TUN/TAP adapters; system proxy settings
- listening-port summaries
- Windows Services (non-system, non-Microsoft only)
- Docker Desktop summary
- IIS and WinRM status
- startup items and user-created scheduled tasks
- manually installed global executable tools (winget / scoop / chocolatey / manual)
- meaningful change history

It does **not** record low-value static inventory such as OS version, CPU, memory, disks, or full process listings by default. SQL Server is explicitly out of scope.

## When To Use It

Use this skill when:

- a Windows host needs an initial ops inventory
- software was installed, upgraded, removed, or reconfigured
- network configuration or proxy/VPN state changed
- Docker, IIS, or WinRM configuration changed
- you need shared docs that multiple agent runtimes can update safely

## Main Modes

### Full inventory

Use when building or refreshing the whole host record.

Run:

```bash
python scripts/update_ops_docs.py
```

### Post-install update

Use after another agent finished installing or changing software.

```bash
python scripts/update_ops_docs.py --reason "Installed Ditto clipboard manager"
```

Optionally narrow the scan:

```bash
python scripts/update_ops_docs.py --reason "Configured Clash proxy" --focus network
python scripts/update_ops_docs.py --reason "Installed PowerToys" --focus software
```

## Workflow

1. Read `references/collection-rules.md` if the request might broaden scope.
2. Read `references/software-detection-rules.md` when software tracking rules matter.
3. Run the updater for full inventory or post-install update.
4. Review the resulting docs under `~/.win-ops-doc-maintainer-docs/hosts/<hostname>/`.
5. If the output is too noisy, adjust:
   - `~/.win-ops-doc-maintainer-docs/watchlist.txt`
   - `~/.win-ops-doc-maintainer-docs/ignorelist.txt`
   - `~/.win-ops-doc-maintainer-docs/manual-software.txt`

## Scripts

- `scripts/win_ops_doc_lib.py` — core collection and rendering logic
- `scripts/update_ops_docs.py` — thin CLI wrapper

Collectors return structured dicts. The updater merges domains, applies noise filters, writes current-state docs, and appends only meaningful changes.

## References

- `references/doc-layout.md`
- `references/collection-rules.md`
- `references/software-detection-rules.md`
- `references/safety-and-boundaries.md`

## Boundaries

- Prefer read-only inspection. Never write to the registry or system config.
- Never dump secrets, proxy credentials, private keys, or full connection strings into docs.
- Treat missing commands or permission failures as partial data, not fatal errors.
