#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/common.sh"
require_python3
python3 "$(script_dir)/ops_doc_lib.py" collect network
