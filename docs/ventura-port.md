# Ventura compatibility port — first pass

Branch: `ventura-support`. Based on `3d6548c`.

This is an unbuilt source port, not a verified Ventura release. The original checkout
at `/Users/craig/Code/3rd-party/cra` has not been changed.

## Changes

- Target macOS 13 in the app, CraCore, helpers, Dock plug-in and installer.
- Pin Swift Perception 2.0.12 in both Swift packages. Migrate observable models,
  ignored properties and manual change tracking in the app and CraCore together.
- Use Perception's bindable wrapper and environment backport, with tracking scopes
  around SwiftUI bodies/helpers and deferred list/presentation builders. Tracking
  must be checked interactively; syntax checks cannot prove views update correctly.
- Use Ventura's single-value `onChange` API. Populate the custom DNS field on
  appearance as well as subsequent changes.
- Replace the Sonoma-only snappy animation with a short ease-out animation.
- Fall back to the older application activation method when exporting diagnostics.
- Provide a static Perception test-support product and macro/compiler flags for
  standalone test harnesses that compile migrated source files directly.
- Keep lint checking direct calls to observation tracking after their rename.

## Binary audit

The downloaded Intel CEF 156.0.27 / Chromium 156.0.8078.96 framework and its
sandbox, Vulkan and SwiftShader libraries declare a minimum macOS version of 13.0.
This was static inspection, not a framework load or browser test.

A locally installed copy of Sparkle 2.10.0 (inside Flecha) and its helper binaries
declare macOS 12.0. That copy has not been matched against Cra's pinned archive.

## Validation so far

- Repository lint passes.
- Shell syntax checks pass.
- The shipped-issue guard passes: 590 locked tests for 142 issues are unchanged.
  This guard checks test definitions; it does not execute those tests.
- `git diff --check` passes.
- The installed Swift 5.9 parser reports the same diagnostic set for the original
  app and this port, with no new diagnostics. Existing newer Swift syntax is not
  understood by that compiler. This is not a type check or macro-expansion check.
- `swift test --package-path Packages/CraCore` is blocked: this Mac has Xcode 15.2 /
  Swift 5.9.2, whereas the manifests require Swift tools 5.10. The documented
  build environment remains Xcode 16 or newer.
- GitHub downloads from the command environment fail DNS resolution, so the
  Perception package and its macro have not been resolved or built here.

## Next build on a newer Mac

Use Xcode 16+ with a compatible Swift toolchain and working GitHub access:

```sh
swift package resolve
swift test --package-path Packages/CraCore
scripts/test.sh
CRA_ARCH=x86_64 scripts/build.sh debug
```

The first build must validate the pinned Perception API integration, macro
expansion, environment overloads, test-support archive and helper paths, and
report any additional SDK availability errors. The standalone test flags are
provisional until that build succeeds. Do not treat this branch as release-ready.

For runtime testing on Ventura, use a separate disposable profile:

```sh
CRA_DATA_DIR=/tmp/cra-ventura-test-profile build/x86_64/Cra.app/Contents/MacOS/Cra
```

On an Intel build host the output is `build/Cra.app` instead. Test onboarding,
spaces, per-tab sidebar updates, settings/bindings, DNS field initialisation,
command bar, dialogs, downloads, extensions, audio/video and helper processes.
Run launch smoke tests, and confirm no Perception tracking warnings appear in a
debug session. Test updates separately with an isolated update feed; a custom
Ventura build must not replace itself with an upstream Sonoma-only release.

## GitHub fork and build workflow

Fork: https://github.com/craigharman/cra

The `Ventura backport` workflow runs on pushes to `ventura-support` and supports
manual runs once the workflow is registered by GitHub. It uses `macos-15-intel`
with Xcode 16.4. Separate jobs run the tests and build the app, so a test failure
still leaves build diagnostics available. No signing secrets or release writes
are required. An initial fork may require enabling Actions in its Actions tab.

The build verifies the ad-hoc signature and checks that every bundled Mach-O
binary contains Intel code and targets macOS 13.0 or earlier. The artifact
`Cra-Ventura-Intel` contains an app ZIP and SHA-256 checksum. It is experimental,
ad-hoc signed and not notarized. This workflow does not publish a GitHub release,
run the app, or access your real browser profile. Its run is not a Ventura runtime
test; the hosted machine runs a newer macOS.

The development build disables the upstream update feed. On Ventura, extract
the downloaded app and start it with an isolated profile:

```sh
CRA_DATA_DIR=/tmp/cra-ventura-test-profile /path/to/Cra.app/Contents/MacOS/Cra
```
