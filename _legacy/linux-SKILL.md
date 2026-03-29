---
name: ops-doc-maintainer
description: Maintain hotspot-only Linux operations documentation for a host. Use when you need to inventory network ports, Docker, Nginx, SSH, PostgreSQL, or manually installed global CLI tools, and when another agent has just installed or changed software and the shared ops docs must be updated.
---

# Ops Doc Maintainer

Keep this skill portable. The core workflow must stay compatible with Codex, Claude Code, and OpenClaw.

## What This Skill Maintains

This skill updates shared host docs in:

- `$OPS_DOCS_HOME` when set
- otherwise `~/.ops-doc-maintainer-docs/`

It records only hotspot information:

- network and listening-port summaries
- Docker, Nginx, SSH, and PostgreSQL summaries
- manually installed global executable tools
- meaningful change history

For PostgreSQL, keep only connection guidance and config-path references. Do not inventory databases, users, or live connections.

It does **not** record low-value static inventory such as OS, kernel, CPU, memory, disks, or mounts by default.

## When To Use It

Use this skill when:

- a host needs an initial ops inventory
- software was installed, upgraded, removed, or reconfigured
- Docker, Nginx, SSH, or PostgreSQL changed
- you need shared docs that multiple agent runtimes can update safely

## Main Modes

### Full inventory

Use when building or refreshing the whole host record.

Run:

```bash
python3 scripts/update_ops_docs.py
```

### Post-install update

Use after another agent finished installing or changing software.

Run:

```bash
python3 scripts/update_ops_docs.py --reason "Installed or changed software"
```

Optionally narrow the summary:

```bash
python3 scripts/update_ops_docs.py --reason "Installed PostgreSQL client tools" --focus software --focus services
```

## Workflow

1. Read `references/collection-rules.md` if the request might broaden scope.
2. Read `references/software-detection-rules.md` when software tracking rules matter.
3. Run the updater for full inventory or post-install update.
4. Review the resulting docs under `~/.ops-doc-maintainer-docs/hosts/<hostname>/`.
5. If the output is too noisy, adjust:
   - `~/.ops-doc-maintainer-docs/watchlist.txt`
   - `~/.ops-doc-maintainer-docs/ignorelist.txt`
   - `~/.ops-doc-maintainer-docs/manual-software.txt`

## Scripts

- `scripts/collect_network_hotspots.sh`
- `scripts/collect_service_hotspots.sh`
- `scripts/collect_postgres_hotspots.sh`
- `scripts/collect_software_tools.sh`
- `scripts/update_ops_docs.py`

Collectors print JSON for one domain. The updater merges domains, applies noise filters, writes current-state docs, and appends only meaningful changes.

## References

- `references/doc-layout.md`
- `references/collection-rules.md`
- `references/software-detection-rules.md`
- `references/safety-and-boundaries.md`

## Boundaries

- Prefer read-only inspection.
- Never dump secrets, private keys, or full connection strings into docs.
- Treat missing commands or permission failures as partial data, not fatal errors.
