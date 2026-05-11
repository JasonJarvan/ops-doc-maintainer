# Software Detection Rules

Track only manually installed global executable tools and user-managed packages.

Allowed sources:

- `winget`: packages from `winget list --source winget`; filter to top-level user-installed entries
- `scoop`: apps from `scoop list`
- `chocolatey`: packages from `choco list --local-only --limit-output`
- `manual-software.txt`: manually maintained list for hand-installed tools not detected by any manager

Do not track:

- Windows built-in components and system apps
- dependency-only packages installed as side-effects
- libraries without executable entry points
- Microsoft Store apps unless explicitly added to watchlist
- SQL Server or database server components (out of scope)

Recommended software fields:

- name
- id (winget package ID when available)
- version
- source (winget / scoop / chocolatey / manual)
- notes when supplied manually

Change detection:

- record installs, removals, and version bumps
- ignore version-string-only changes that do not represent a real upgrade (e.g. timestamp suffixes)
