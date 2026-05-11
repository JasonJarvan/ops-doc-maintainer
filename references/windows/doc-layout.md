# Doc Layout

Shared docs home:

- `$WIN_OPS_DOCS_HOME`
- fallback `$OPS_DOCS_HOME`
- fallback `~/.win-ops-doc-maintainer-docs/`

Layout:

```text
~/.win-ops-doc-maintainer-docs/
├── watchlist.txt
├── ignorelist.txt
├── manual-software.txt
└── hosts/
    └── <hostname>/
        ├── index.md
        ├── network.md
        ├── services.md
        ├── software.md
        ├── changes.md
        └── snapshots/
            └── latest.json
```

Rules:

- `index.md` summarizes the current host state.
- `network.md`, `services.md`, and `software.md` contain current state only (overwritten each run).
- `changes.md` is append-only history and records only meaningful changes.
- `snapshots/latest.json` stores normalized machine-readable state used for diffing.

Config files (in docs home root):

- `watchlist.txt`: force-keep tracked items even if they would normally be filtered.
- `ignorelist.txt`: suppress noisy items from docs and diffing.
- `manual-software.txt`: add hand-installed global tools that package managers cannot detect.
