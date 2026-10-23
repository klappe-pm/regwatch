#!/usr/bin/env bash
# Build the pages behind `regwatch ui` and copy the static export into regwatch/web/.
#
# Installs the exact versions in web/package-lock.json (npm ci), then runs the build,
# which writes the export to web/out/ and replaces regwatch/web/ with it. Commit the
# changed files under regwatch/web/ with the source change, so a pip install needs no Node.
set -euo pipefail

for tool in node npm; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "build-web: $tool is not on PATH; install Node.js 22 or newer" >&2
    exit 1
  }
done

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NEXT_TELEMETRY_DISABLED=1
npm --prefix "$root/web" ci --ignore-scripts --no-audit --no-fund
npm --prefix "$root/web" run build
echo "build-web: regwatch/web/ is up to date; commit it with your change"
