# OpenClaw Adapter Notes

- Treat this directory as the portable source of truth.
- Add only thin OpenClaw metadata when copying into an OpenClaw skill directory.
- Do not fork the workflow logic unless runtime constraints force it.
- Keep the same shared docs root:
  - `$OPS_DOCS_HOME`
  - fallback `~/.ops-doc-maintainer-docs/`
- Typical OpenClaw use:
  - initial host inventory
  - post-install documentation refresh
