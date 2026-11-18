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

## Releases: following upstream automatically

Fork: https://github.com/craigharman/cra, default branch `ventura-support`.

`.github/workflows/ventura-sync.yml` checks VictorKildahl/cra once a day for a new `vX.Y.Z`
tag. It merges the tag into `ventura-support` (`-X ignore-space-change`), runs
`scripts/ventura-perceptify.py` so upstream's new views follow the rules above, then lints,
tests, builds the Intel app and checks it with `scripts/verify-ventura-bundle.py`. When all of
that passes it pushes, and tags the same version here, which starts `release.yml`. A conflict
or a failure pushes nothing; the run's summary says what to fix.

Rules that keep that merge clean:

- Lines inside `WithPerceptionTracking { }` keep upstream's indentation. Re-indenting them
  would make every upstream edit to those views a conflict.
- A new Ventura rule goes in `scripts/ventura-perceptify.py`, not in a hand edit, so the next
  release gets it too. `scripts/ventura-perceptify.py --check` lists files it would change.
- Releases built here read this fork's update feed (`scripts/build.sh`, `GITHUB_REPOSITORY`)
  and its own Sparkle key (`SPARKLE_PUBLIC_KEY` variable, `SPARKLE_PRIVATE_KEY` secret), so a
  Ventura copy never updates itself to an upstream build that needs macOS 14.

The repository variable `CRA_ALLOW_OLD_ENGINE=1` lets `release.sh` ship the engine (upstream's
Chromium framework, `scripts/fetch-engine.sh`) that upstream's release pinned, even when Chrome
stable has moved on; without it most releases stop there. The engine's binaries target macOS 13,
and `scripts/verify-ventura-bundle.py` checks them with the rest of the app.

Upstream's scheduled workflows (Nightly, CEF updates, Ideas housekeeping) are disabled in the
fork's Actions settings.

For runtime testing on Ventura, use a separate profile:

```sh
CRA_DATA_DIR=/tmp/cra-ventura-test-profile /path/to/Cra.app/Contents/MacOS/Cra
```
