# Doc Layout

Shared docs home:

- `$OPS_DOCS_HOME`
- fallback `~/.ops-doc-maintainer-docs/`

Layout:

```text
~/.ops-doc-maintainer-docs/
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
- `network.md`, `services.md`, and `software.md` contain current state only.
- `changes.md` is history and only records meaningful changes.
- `snapshots/latest.json` stores normalized machine-readable state used for diffing.

Config files:

- `watchlist.txt`: force-keep tracked items even if they would normally be filtered.
- `ignorelist.txt`: suppress noisy items from docs and diffing.
- `manual-software.txt`: add hand-installed global tools that package managers cannot detect.
