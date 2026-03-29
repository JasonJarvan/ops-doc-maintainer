#!/usr/bin/env bash
set -euo pipefail

ops_docs_home() {
  printf '%s\n' "${OPS_DOCS_HOME:-$HOME/.ops-doc-maintainer-docs}"
}

ops_host_name() {
  hostname -s 2>/dev/null || hostname
}

script_dir() {
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd
}

require_python3() {
  command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required" >&2
    exit 1
  }
}
