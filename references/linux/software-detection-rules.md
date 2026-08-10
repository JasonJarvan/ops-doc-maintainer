# Software Detection Rules

Track only manually installed global executable tools.

Allowed sources:

- `apt`: (Linux) from `apt-mark showmanual`, filtered to packages that expose global executables
- `snap`: (Linux) only snaps that expose command names
- `homebrew`: (macOS) Homebrew itself, plus `brew leaves --installed-on-request` formulae that expose executables under `$(brew --prefix)/opt/<formula>/{bin,sbin}` — never the full dependency closure
- `homebrew-cask`: (macOS) `brew list --cask` entries, recorded separately from formulae
- `npm`: only global top-level CLI packages
- `pip`: only top-level requested packages with console scripts
- `uv`: only `uv tool` installs
- `conda`: only explicit history packages with console scripts
- `manual-binary`: manually maintained list for hand-installed tools

Do not track:

- dependency-only packages
- libraries without executable entry points
- system-default utilities unless they were explicitly installed later and detected as manual tools
- Docker images as host-installed software

Recommended software fields:

- name
- source
- version
- executables
- config paths when known
- notes when supplied manually
