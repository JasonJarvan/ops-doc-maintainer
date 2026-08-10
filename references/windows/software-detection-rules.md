# Software Detection Rules

Track only manually installed global executable tools and user-managed packages.

Allowed sources:

- `winget`: packages from `winget list --source winget`; filter to top-level user-installed entries
- `scoop`: apps from `scoop list`
- `chocolatey`: packages from `choco list --local-only --limit-output`
- `npm-global`: global top-level CLI packages that declare a `bin` entry point
- `pip`: top-level requested packages (`pip list --not-required`) that expose console scripts
- `uv`: `uv tool list` installs
- `manual-software.txt`: manually maintained list for hand-installed tools not detected by any manager

Parsing notes:

- `winget list` renders a localised, fixed-width table. Never key off the English
  header words, and never split rows on whitespace runs: package names legitimately
  contain double spaces, and CJK names make character offsets diverge from display
  columns. Anchor on the undashed separator line, then slice by display width.
- npm, scoop, and similar tools ship as `.cmd` shims on Windows; resolve them through
  `PATH`/`PATHEXT` before spawning, or the collector silently reports nothing.

Do not track:

- Windows built-in components and system apps
- dependency-only packages installed as side-effects
- libraries without executable entry points
- Microsoft Store apps unless explicitly added to watchlist
- SQL Server or database server components (out of scope)
- shared runtimes and redistributables pulled in as dependencies: `Microsoft.VCRedist.*`,
  `Microsoft.VCLibs.*`, `Microsoft.UI.Xaml.*`, `Microsoft.DotNet.*Runtime*`,
  `Microsoft.WindowsAppRuntime*`, `Microsoft.EdgeWebView*`
- chocolatey packaging artefacts: `KB<number>` update payloads, `vcredist*`,
  `*.extension` helper packages, and chocolatey itself

Recommended software fields:

- name
- id (winget package ID when available)
- version
- executables (npm / pip / uv entry points)
- source (winget / scoop / chocolatey / npm-global / pip / uv / manual)
- notes when supplied manually

Caps:

- winget output is capped at 300 rows. If the cap is hit, the doc records an explicit
  `(truncated at N entries)` marker — a cap must never read as a complete inventory.

Change detection:

- record installs, removals, and version bumps
- ignore version-string-only changes that do not represent a real upgrade (e.g. timestamp suffixes)
