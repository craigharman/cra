#!/bin/bash
# Sourced by the standalone test harnesses after cd to the repository root.
# SwiftPM supplies both the Perception runtime archive and its macro executable.
# Keep these flags in an array so checkout paths containing spaces work.
if [ -z "${CRA_PERCEPTION_TEST_BIN:-}" ]; then
  CRA_PERCEPTION_TEST_BIN="$(swift build --package-path Packages/CraCore --show-bin-path)" || exit 1
  swift build --package-path Packages/CraCore --product CraPerceptionTestSupport >&2 || exit 1
  export CRA_PERCEPTION_TEST_BIN
fi
CRA_PERCEPTION_MACRO="$CRA_PERCEPTION_TEST_BIN/PerceptionMacros-tool"
if [ ! -x "$CRA_PERCEPTION_MACRO" ]; then
  CRA_PERCEPTION_MACRO="$CRA_PERCEPTION_TEST_BIN/PerceptionMacros"
fi
if [ ! -x "$CRA_PERCEPTION_MACRO" ]; then
  echo "Perception's compiler macro was not built. Use the documented Xcode 16+ toolchain." >&2
  exit 1
fi
# Compile for macOS 13 like the app: on a newer target Perception turns its Ventura API off.
# Harnesses that build stub modules pass $CRA_TEST_TARGET to those too.
CRA_TEST_TARGET="$(uname -m)-apple-macos13.0"
CRA_PERCEPTION_SWIFTC_FLAGS=(
  -target "$CRA_TEST_TARGET"
  # Older SwiftPM puts modules in Modules/, newer (Swift 6.2+) next to the products.
  -I "$CRA_PERCEPTION_TEST_BIN/Modules"
  -I "$CRA_PERCEPTION_TEST_BIN"
  -load-plugin-executable "$CRA_PERCEPTION_MACRO#PerceptionMacros"
  "$CRA_PERCEPTION_TEST_BIN/libCraPerceptionTestSupport.a"
)
