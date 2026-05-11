# Claude Code Adapter Notes

- Keep `SKILL.md`, `scripts/`, `references/`, and `assets/` unchanged.
- The skill file installed to `~/.claude/skills/win-ops-doc-maintainer.md` should mirror `SKILL.md` frontmatter.
- Docs root follows the same convention as the Linux version:
  - `$WIN_OPS_DOCS_HOME` or `$OPS_DOCS_HOME`
  - fallback `~/.win-ops-doc-maintainer-docs/`
- Run scripts with `python` (not `python3`) on Windows to match the default PATH.
- Recommended trigger phrases:
  - "refresh Windows ops docs"
  - "update host inventory"
  - "record this software install in ops docs"
  - "update network docs" (use `--focus network` implicitly)
