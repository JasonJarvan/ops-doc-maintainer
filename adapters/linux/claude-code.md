# Claude Code Adapter Notes

- Keep `SKILL.md`, `scripts/`, `references/`, and `assets/` unchanged.
- If Claude Code packaging wants extra frontmatter, add it in the Claude-specific installed copy rather than changing the portable source skill.
- Use the same shared docs root:
  - `$OPS_DOCS_HOME`
  - fallback `~/.ops-doc-maintainer-docs/`
- Recommended trigger phrases:
  - "refresh ops docs"
  - "update host inventory"
  - "record this software install in ops docs"
