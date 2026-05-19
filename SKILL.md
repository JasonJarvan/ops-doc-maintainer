---
name: ops-doc-maintainer
description: Maintain hotspot-only operations documentation for a host (Linux or Windows). Use when you need to inventory network/listening-port state, VPN/proxy (Clash, WireGuard, etc.), Docker, Nginx/IIS, SSH/WinRM, PostgreSQL (Linux only), Windows Services, or manually installed global CLI tools, and when another agent has just installed or changed software and the shared ops docs must be updated. Cross-platform: auto-detects Linux vs Windows on every invocation.
---

# Ops Doc Maintainer

Cross-platform skill that keeps low-noise, hotspot-only ops documentation for the local host. Auto-routes to the Linux or Windows implementation on every invocation. Designed to stay portable across Codex, Claude Code, and OpenClaw.

## Platform Routing

On every invocation, detect the host platform and use the matching subtree:

| Platform | Subtree | Library | Docs home |
|---|---|---|---|
| Linux/macOS | `scripts/linux/`, `references/linux/`, `adapters/linux/`, `agents/linux/`, `assets/linux/` | `ops_doc_lib.py` | `$OPS_DOCS_HOME` else `~/.ops-doc-maintainer-docs/` |
| Windows | `scripts/windows/`, `references/windows/`, `adapters/windows/`, `agents/windows/`, `assets/windows/` | `win_ops_doc_lib.py` | `$WIN_OPS_DOCS_HOME` or `$OPS_DOCS_HOME` else `~/.win-ops-doc-maintainer-docs/` |

Detection rule: `python -c "import platform; print(platform.system())"` → `Linux`/`Darwin` use Linux subtree, `Windows` uses Windows subtree. The dispatcher script `scripts/update_ops_docs.py` does this automatically — prefer it over invoking the subtree directly.

## What This Skill Maintains

Hotspot-only host docs. Records change history, never low-value static inventory (OS, CPU, memory, disks).

**Common to both platforms:**

- network and listening-port summaries
- Docker summary
- manually installed global executable tools
- meaningful change history

**Linux-specific:** Nginx, SSH, PostgreSQL (connection guidance and config paths only — no databases/users/connections).

**Windows-specific:** network adapters with VPN/proxy detection (Clash, Mihomo, WireGuard, V2Ray, TUN/TAP, system proxy), Windows Services (non-system/non-Microsoft only), IIS, WinRM, startup items, user-created scheduled tasks. SQL Server is explicitly out of scope.

## When To Use It

- a host needs an initial ops inventory
- software was installed, upgraded, removed, or reconfigured
- network/proxy/VPN state changed
- Docker, Nginx/IIS, SSH/WinRM, or PostgreSQL changed
- you need shared docs that multiple agent runtimes can update safely

## Main Modes

### Full inventory

```bash
python3 scripts/update_ops_docs.py
```

### Post-install update

```bash
python3 scripts/update_ops_docs.py --reason "Installed or changed software"
```

### Focused scan

```bash
python3 scripts/update_ops_docs.py --reason "Configured Clash proxy" --focus network
python3 scripts/update_ops_docs.py --reason "Installed PowerToys" --focus software
```

Valid `--focus` values:

- Linux: `network`, `services`, `software`, `postgresql`
- Windows: `network`, `services`, `software`

The dispatcher forwards `--focus` to the platform implementation, which validates choices.

## Workflow

1. Detect platform (the dispatcher handles this automatically).
2. Read `references/<platform>/collection-rules.md` if the request might broaden scope.
3. Read `references/<platform>/software-detection-rules.md` when software tracking rules matter.
4. Run the dispatcher for full inventory or post-install update.
5. Review the resulting docs under the platform's docs home / `hosts/<hostname>/`.
6. If the output is too noisy, adjust files in the docs home:
   - `watchlist.txt`
   - `ignorelist.txt`
   - `manual-software.txt`

## Scripts

- `scripts/update_ops_docs.py` — cross-platform dispatcher (detects OS, delegates).
- `scripts/linux/` — bash collectors + `ops_doc_lib.py` updater.
- `scripts/windows/` — `win_ops_doc_lib.py` (Python + PowerShell subprocess) + entry CLI.

Collectors return structured data for one domain. The platform updater merges domains, applies noise filters, writes current-state docs, and appends only meaningful changes.

## References

Platform-specific (paths inside `references/<platform>/`):

- `doc-layout.md`
- `collection-rules.md`
- `software-detection-rules.md`
- `safety-and-boundaries.md`

## Adapters / Agents

- `adapters/<platform>/claude-code.md` — Claude Code adapter notes.
- `adapters/linux/openclaw.md` — OpenClaw adapter (Linux only).
- `agents/<platform>/openai.yaml` — OpenAI Codex agent spec.

## Boundaries

- Prefer read-only inspection. On Windows, never write to the registry or system config.
- Never dump secrets, proxy credentials, private keys, or full connection strings into docs.
- Treat missing commands or permission failures as partial data, not fatal errors.
