# Collection Rules

Collect only high-signal operational data.

Default sections:

- network hotspots
- Docker summary
- Nginx summary
- SSH summary
- PostgreSQL summary
- manually installed global executable tools

Do not collect these by default:

- OS, kernel, CPU, memory, disks, or mounts
- full package inventories
- full logs
- full process listings
- full config file bodies
- secrets, tokens, private keys, or passwords
- PostgreSQL database, user, or connection inventories

Noise reduction:

- current-state docs must overwrite previous current state
- `changes.md` only records meaningful changes
- ignore ordering-only differences
- ignore unchanged status checks
- prefer summaries over raw command output
