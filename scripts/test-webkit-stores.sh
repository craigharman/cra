#!/bin/bash
# WebKitStores in a fresh process, as at launch, before anything has touched WebKit.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/perception-test-flags.sh
TEST_DIR="$(mktemp -d /tmp/cra-webkit-tests.XXXXXX)"
trap 'rm -rf "$TEST_DIR"' EXIT
xcrun swiftc -swift-version 5 -parse-as-library ${CRA_TEST_SWIFTC_FLAGS:-} "${CRA_PERCEPTION_SWIFTC_FLAGS[@]}" \
  Packages/CraCore/Sources/CraCore/*.swift Packages/CraCore/Sources/CraCore/Perf/*.swift Sources/Cra/Perf/Perf.swift \
  Sources/Cra/Services/WebKit/WebKitStores.swift Sources/Cra/Services/Persistence.swift Sources/Cra/Services/CraLog.swift \
  Tests/WebKitStoresTests.swift -o "$TEST_DIR/webkit-tests"
"$TEST_DIR/webkit-tests"
[ -z "${CRA_TEST_KEEP:-}" ] || cp "$TEST_DIR/webkit-tests" "$CRA_TEST_KEEP/"
