#!/usr/bin/env bash
# Type-check backend sources against the local API stubs (no network needed).
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=$(mktemp -d)
trap 'rm -rf "$OUT"' EXIT

echo "compiling stubs..."
javac -nowarn -d "$OUT/stubs" $(find tools/typecheck/stubs -name "*.java")

echo "type-checking backend/src/main..."
javac -nowarn -proc:none -cp "$OUT/stubs" -d "$OUT/main" \
  $(find backend/src/main/java -name "*.java")

echo "type-checking backend/src/test..."
javac -nowarn -proc:none -cp "$OUT/stubs:$OUT/main" -d "$OUT/test" \
  $(find backend/src/test/java -name "*.java")

echo "OK — no type errors."
