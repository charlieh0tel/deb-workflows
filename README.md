# deb-workflows

Reusable GitHub Actions workflows for building and testing projects.

## Available Workflows

### Rust

All three Rust workflows take a `toolchain`. Leave it empty (the default) and the
workflow reads `channel` out of the caller's `rust-toolchain.toml`, falling back to
`stable` when there is no such file — so a repo that pins names its version once, in
the file, and CI installs exactly that. Pass a value to override the file for the
*install* only: cargo still obeys `rust-toolchain.toml` when it runs, so a mismatch
just means two toolchains get downloaded. Components and targets are installed onto
whichever toolchain is resolved. The legacy bare `rust-toolchain` file (no `.toml`)
is not read; those repos should pass `toolchain` explicitly.

#### `rust-build-deb.yml`

Builds `.deb` packages using `cargo-deb`. Creates a GitHub Release with `.deb` artifacts when a `v*` tag is pushed.

**Requirements:** `[package.metadata.deb]` section in `Cargo.toml`. See [cargo-deb docs](https://github.com/kornelski/cargo-deb#readme).

**Default targets:** amd64 (`ubuntu-latest`) and arm64 (`ubuntu-22.04-arm`, for Debian bookworm glibc compat).

Each matrix entry's `target` is added with rustup before the build, so a pinned toolchain or a non-host target works without extra setup. A true cross build may still need its linker in `build-deps`.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install |
| `targets` | string | amd64+arm64 | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 |
| `package` | string | `""` | Cargo package to build (`cargo deb -p`). Empty = default package. |
| `artifact-suffix` | string | `""` | Suffix added before arch in artifact name (e.g. `collector` → `debian-package-collector-amd64`). Required when calling this workflow multiple times in one repo to avoid artifact name collisions. |
| `submodules` | string | `"false"` | Checkout submodules: `true`, `false`, or `recursive` |
| `toolchain` | string | `""` | Rust toolchain to install. Empty reads `channel` from the caller's `rust-toolchain.toml`, else `stable`. |
| `audit` | boolean | `true` | Run `cargo audit` before releasing; a finding blocks the release |
| `audit-args` | string | `""` | Extra args for `cargo audit` (e.g. `--ignore RUSTSEC-2024-0001`) |

The audit runs in parallel with the build, but the release job waits for it: on
a tag whose dependencies carry an advisory the build still runs and still
uploads its workflow artifacts, but no GitHub Release is published.
`audit: false` skips the job and releases anyway. See `rust-ci.yml` below for
how the audit itself works.

#### `rust-build-exes.yml`

Builds release binaries for Linux and Windows. Creates a GitHub Release with binary artifacts when a `v*` tag is pushed.

**Default targets:** amd64 Linux, arm64 Linux, x86_64 Windows.

Each matrix entry's `target` is added with rustup before the build, so a pinned toolchain or a non-host target works without extra setup. A true cross build may still need its linker in `build-deps`.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install on Linux |
| `targets` | string | amd64+arm64+win | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 Linux |
| `features` | string | `""` | Comma-separated cargo features to enable for build and test |
| `toolchain` | string | `""` | Rust toolchain to install. Empty reads `channel` from the caller's `rust-toolchain.toml`, else `stable`. |
| `audit` | boolean | `true` | Run `cargo audit` before releasing; a finding blocks the release |
| `audit-args` | string | `""` | Extra args for `cargo audit` (e.g. `--ignore RUSTSEC-2024-0001`) |

The audit runs in parallel with the build, but the release job waits for it: on
a tag whose dependencies carry an advisory the build still runs and still
uploads its workflow artifacts, but no GitHub Release is published.
`audit: false` skips the job and releases anyway. See `rust-ci.yml` below for
how the audit itself works.

#### `rust-ci.yml`

Runs `cargo fmt` (nightly), `cargo clippy`, `cargo test`, and a `cargo audit`
dependency audit as separate parallel jobs.

The clippy and test jobs cache the cargo registry and `target/` between runs.
`cache-directories` extends what the cache keeps: a build script that fetches
sources into `target/` needs its path listed, or the cache prunes it and the
fetch repeats every run.

`check-args` and `test-args` reach clippy and `cargo test` respectively. Pass
`--workspace` in `check-args` for a workspace, or clippy lints the default
package alone.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `toolchain` | string | `""` | Toolchain for clippy/test. Empty reads `channel` from the caller's `rust-toolchain.toml`, else `stable`. |
| `fmt-toolchain` | string | `"nightly"` | Toolchain for `cargo fmt`, invoked as `cargo +<toolchain> fmt` so a pinned `rust-toolchain.toml` does not take it over. Empty resolves like `toolchain`. |
| `targets` | string | `""` | Extra targets to install (e.g. `thumbv6m-none-eabi`) |
| `build-deps` | string | `""` | Space-separated apt packages to install |
| `check-args` | string | `""` | Extra args for cargo check/clippy (e.g. `--target thumbv6m-none-eabi`) |
| `test-args` | string | `""` | Extra args for `cargo test` (e.g. `--features testing`) |
| `cache-directories` | string | `""` | Extra paths for the cargo cache to keep, one per line |
| `audit` | boolean | `true` | Run `cargo audit` against the RustSec advisory database |
| `audit-args` | string | `""` | Extra args for `cargo audit` (e.g. `--ignore RUSTSEC-2024-0001`) |

The `audit` job builds `cargo-audit` once and caches the binary; the advisory
database itself is fetched on every run, so a cached binary never means stale
advisories. A library with no committed `Cargo.lock` gets one generated for the
audit. An advisory fails the job -- set `audit: false` to turn it off, or name
the advisory in `audit-args` to accept one that has no fix yet.

### Python

#### `python-ci.yml`

Runs lint, format check, tests, and an optional dependency audit for Python projects. Each job is independent and can be disabled by passing an empty string for its command.

**uv support:** uv is detected once (a `uv.lock`, `uv.toml`, or a `[tool.uv*]` section in `pyproject.toml` in `working-directory`) and the result is shared by all three jobs. When detected, `uv sync` installs the project's dependencies and `requirements-file` is ignored. Otherwise the pip path is used, unchanged. Override detection with `use-uv`.

Under uv, each command's tool is taken from the **project environment** when it's there (`uv run --no-sync -- ruff check .`), so CI uses the version your lockfile pins rather than whatever is current on PyPI. Declare your tools in a dependency group to get this:

```toml
[dependency-groups]
dev = ["pytest", "ruff"]
```

If the tool isn't in the project's dependencies, it falls back to fetching it ad hoc (`uv run --with ruff -- ...`).

When a `uv.lock` is committed it is treated as authoritative: the sync runs `uv sync --locked`, so a lock that no longer matches `pyproject.toml` fails CI instead of being silently rewritten, and commands run with `--frozen` so a check can never mutate the lock as a side effect. Callers with no lockfile are unaffected (both flags require one to exist). Set `lock-check: false` to opt out.

Make sure `python-version` satisfies your project's `requires-python`. Under uv a mismatch is a hard failure at sync time (`uv sync` has no compatible interpreter), where the pip path would often paper over it — so a project declaring `requires-python = ">=3.13"` must pass `python-version: "3.13"` explicitly, since the default is 3.12.

Each command must **start with the tool name** — `ruff check .`, not `MPLBACKEND=Agg python foo.py`. The command is word-split out of a variable, so a leading `VAR=value` is read as the program name rather than an assignment (this is true on both the uv and pip paths). Set variables in your caller's `env:` or inside the script being run; passing one as a prefix fails the job with an explicit error.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-version` | string | `"3.12"` | Python version |
| `working-directory` | string | `"."` | Directory all commands run in (also where uv detection looks) |
| `use-uv` | string | `"auto"` | `auto` (detect), `true` (force uv), or `false` (force pip) |
| `lock-check` | string | `"auto"` | Assert the lockfile is up to date: `auto` (strict when `uv.lock` exists), `true`, `false`. uv only. |
| `system-packages` | string | `""` | Space-separated apt packages installed before dependencies (e.g. `libportaudio2` for `sounddevice`) |
| `requirements-file` | string | `"requirements.txt"` | Path to requirements file, relative to `working-directory` (empty to skip; ignored under uv) |
| `test-command` | string | `"pytest --showlocals -rA"` | Test command (empty to skip tests) |
| `lint-command` | string | `"ruff check ."` | Lint command (empty to skip lint) |
| `format-check-command` | string | `"ruff format --check ."` | Format check command (empty to skip) |
| `audit-command` | string | `""` | Dependency audit command, e.g. `pip-audit`. Off unless set. |

Unlike the Rust and Go audits, this one is opt-in. The job installs the
project's dependencies the same way `test` does and then audits what is
installed, and with no arguments `pip-audit` reports on the entire environment
-- under uv that is just the locked project environment, but on the pip path it
also covers whatever the runner's interpreter came with, which is a poor reason
to fail somebody's build. Set `audit-command: pip-audit` to turn it on. Like the
other commands it is just a command, so `pip-audit --ignore-vuln GHSA-xxxx-xxxx-xxxx`
accepts a finding that has no fix yet.

### Debian (dpkg)

#### `dpkg-build-deb.yml`

Builds `.deb` packages from projects with a `debian/` directory using `jtdor/build-deb-action` and `dpkg-buildpackage`. Creates a GitHub Release with `.deb` artifacts when a `v*` tag is pushed.

**Requirements:** A `debian/` directory with standard Debian packaging files (`control`, `rules`, `changelog`, etc.).

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `extra-build-deps` | string | `"devscripts git"` | Extra build dependencies |
| `before-build-hook` | string | `""` | Command to run before building |
| `os` | string | `"ubuntu-latest"` | Runner OS |
| `artifact-name` | string | `"debian-package"` | Name for the uploaded artifact |

### Go

#### `go-ci.yml`

Runs `go build`, `go test`, and `go vet`, plus a `govulncheck` audit.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `go-version` | string | `"stable"` | Go version |
| `audit` | boolean | `true` | Run `govulncheck` against the Go vulnerability database |
| `audit-args` | string | `"./..."` | Arguments for `govulncheck` |

`govulncheck` reports only vulnerabilities in code paths the build actually
reaches, so it is quiet by comparison with a manifest scanner. A finding fails
the job; `audit: false` turns it off.

## Practices

[docs/best-practices.md](docs/best-practices.md) collects the rules these
workflows assume: pinning, permissions, toolchains, advisories, releases and
trusted publishing, each with the failure that earned it. Read it before
changing a workflow or cutting a release.

## Versioning

Pin callers to the `v1` major tag:

```yaml
uses: charlieh0tel/deb-workflows/.github/workflows/python-ci.yml@v1
```

`v1` is a moving tag, re-pointed at each release the way `actions/checkout@v5` works: you get fixes without editing caller repos, and a breaking change would ship as `v2`. `@main` also works if you want the tip.

`python-ci.yml` loads this repo's composite actions (`setup-python-ci`, `uv-sync`, `uv-run`) from the commit the workflow file itself came from: each job checks this repository out at `job.workflow_sha` into `.deb-workflows/` and uses `./.deb-workflows/.github/actions/...`. A caller on `@v1` therefore gets v1's actions, and a pull request against this repo gets its own -- no tag has to move for a change under `.github/actions/` to be tested.

Two things follow when working on this repo:

- The jobs check the caller out themselves, before fetching `.deb-workflows`; a root checkout wipes a non-empty workspace, so the order matters. That is why `setup-python-ci` does not check out.
- `job.workflow_sha` is not in GitHub's contexts reference and is unknown to actionlint, so `.github/actionlint.yaml` suppresses the unknown-property error for that one file.

Moving `v1` is still how a release reaches callers:

```sh
# -a keeps v1 an annotated tag; a bare `git tag -f` would demote it.
git tag -f -a v1 -m "v1" && git push -f origin v1
```

### Pinned third-party actions

Every third-party `uses:` in this repo is pinned to a full commit SHA, with the tag it came from in a trailing comment:

```yaml
- uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
```

A tag can be moved; a SHA cannot, so a compromised upstream tag can't silently change what runs here. `.github/dependabot.yml` opens a weekly grouped PR that bumps the SHAs and their comments together. Keep the comment accurate when hand-editing a pin — it is the only human-readable record of the version.

`dtolnay/rust-toolchain` is pinned the same way, so the toolchain can no longer come from the branch name (`@stable`): every call site passes `toolchain:` explicitly. The action requires a channel and does not read `rust-toolchain.toml`, which is why each Rust job resolves one from the file first. That resolution is inlined in every job on purpose -- a reusable workflow runs in the *caller's* checkout, so it cannot call a script or composite action from this repo without checking this repo out as well (the dance `python-ci.yml` does above).

This repo's own refs are not SHA-pinned and should not be: `test-released.yml` exists to exercise the published `@v1` tag, and the `./` paths in the other test workflows exist to exercise the working tree.

## How to Adopt

### Step 1: Choose a workflow

| Goal | Workflow |
|------|---------|
| Rust `.deb` packages (cargo-deb) | `rust-build-deb.yml` |
| Rust release binaries (Linux + Windows) | `rust-build-exes.yml` |
| Rust CI (fmt, clippy, test) | `rust-ci.yml` |
| Debian `.deb` packages (dpkg) | `dpkg-build-deb.yml` |
| Python CI (lint, format, test) | `python-ci.yml` |
| Go CI (build, test, vet) | `go-ci.yml` |

You can combine multiple workflows in a single repo (e.g. `rust-ci.yml` + `rust-build-deb.yml`).

### Step 2: Create the caller workflow

Create `.github/workflows/ci.yml` (or `build.yml`, etc.) in your repo.

#### Rust deb build (minimal):
```yaml
name: Build Debian Package

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

permissions:
  contents: write

jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@v1
    secrets: inherit
```

#### Rust deb build with native deps:
```yaml
jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@v1
    with:
      build-deps: "libdbus-1-dev libasound2-dev"
    secrets: inherit
```

#### Rust deb build (multi-package workspace):
```yaml
permissions:
  contents: write

jobs:
  build-deb-collector:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@v1
    with:
      package: my-collector
      artifact-suffix: collector
    secrets: inherit

  build-deb-agent:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@v1
    with:
      package: my-agent
      artifact-suffix: agent
    secrets: inherit
```

#### Rust binary releases (no deb):
```yaml
jobs:
  build-release:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-exes.yml@v1
    secrets: inherit
```

#### Rust CI only:
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-ci.yml@v1
```

#### Rust CI for embedded (custom target):
```yaml
jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-ci.yml@v1
    with:
      targets: "thumbv6m-none-eabi"
      check-args: "--target thumbv6m-none-eabi"
```

#### Python CI:
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/python-ci.yml@v1
```

#### Python CI (lint only, no tests):
```yaml
jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/python-ci.yml@v1
    with:
      test-command: ""
```

#### Go CI:
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/go-ci.yml@v1
```

#### Debian package (dpkg, for projects with debian/ directory):
```yaml
name: Build Debian Package

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

permissions:
  contents: write

jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/dpkg-build-deb.yml@v1
    with:
      before-build-hook: debchange --controlmaint --local="+ci${{ github.run_id }}~git$(git rev-parse --short HEAD)" "CI build"
    secrets: inherit
```

#### amd64-only deb (e.g. for an x86 server):
```yaml
jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@v1
    with:
      targets: '[{"target":"x86_64-unknown-linux-gnu","os":"ubuntu-22.04","arch":"amd64"}]'
    secrets: inherit
```

### Step 3: Required fields for build/release workflows

Caller workflows that create releases **must** include:
- `permissions: contents: write` at the top level.
- `secrets: inherit` on the job.

CI-only workflows (`rust-ci`, `python-ci`, `go-ci`) do not need these.

### Step 4: For deb builds, add cargo-deb metadata

Add a `[package.metadata.deb]` section to `Cargo.toml`:

```toml
[package.metadata.deb]
maintainer = "Your Name <you@example.com>"
copyright = "2025, Your Name"
license-file = ["LICENSE", "4"]
extended-description = "Description of your project."
section = "utility"
priority = "optional"
depends = "$auto"
assets = [
    ["target/release/my-binary", "usr/bin/", "755"],
    ["README.md", "usr/share/doc/my-project/", "644"],
]
```

### Step 5: Create a release

Push a tag to trigger the release job:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Target matrix format (Rust build workflows)

Each entry in the `targets` JSON array must have:

| Field | Description |
|-------|-------------|
| `target` | Rust target triple (e.g. `x86_64-unknown-linux-gnu`) |
| `os` | GitHub runner (e.g. `ubuntu-latest`, `ubuntu-22.04-arm`, `windows-latest`) |
| `arch` | Architecture label for artifact naming (e.g. `amd64`, `arm64`) |

## Notes

- arm64 Linux builds use `ubuntu-22.04-arm` (native runner) for Debian bookworm glibc compatibility (glibc 2.35).
- amd64 Linux builds use `ubuntu-latest`.
- Cargo registry, git index, and build artifacts are cached for Rust workflows.

## License

MIT
