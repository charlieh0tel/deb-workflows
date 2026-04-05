# deb-workflows

Reusable GitHub Actions workflows for building and testing projects.

## Available Workflows

### Rust

#### `rust-build-deb.yml`

Builds `.deb` packages using `cargo-deb`. Creates a GitHub Release with `.deb` artifacts when a `v*` tag is pushed.

**Requirements:** `[package.metadata.deb]` section in `Cargo.toml`. See [cargo-deb docs](https://github.com/kornelski/cargo-deb#readme).

**Default targets:** amd64 (`ubuntu-latest`) and arm64 (`ubuntu-22.04-arm`, for Debian bookworm glibc compat).

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install |
| `targets` | string | amd64+arm64 | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 |

#### `rust-build-exes.yml`

Builds release binaries for Linux and Windows. Creates a GitHub Release with binary artifacts when a `v*` tag is pushed.

**Default targets:** amd64 Linux, arm64 Linux, x86_64 Windows.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install on Linux |
| `targets` | string | amd64+arm64+win | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 Linux |

#### `rust-ci.yml`

Runs `cargo fmt` (nightly), `cargo clippy`, and `cargo test` as separate parallel jobs.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `toolchain` | string | `"stable"` | Rust toolchain for clippy/test |
| `fmt-toolchain` | string | `"nightly"` | Toolchain for cargo fmt |
| `targets` | string | `""` | Extra targets to install (e.g. `thumbv6m-none-eabi`) |
| `build-deps` | string | `""` | Space-separated apt packages to install |
| `check-args` | string | `""` | Extra args for cargo check/clippy (e.g. `--target thumbv6m-none-eabi`) |

### Python

#### `python-ci.yml`

Runs lint, format check, and tests for Python projects. Each job is independent and can be disabled by passing an empty string for its command.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `python-version` | string | `"3.12"` | Python version |
| `requirements-file` | string | `"requirements.txt"` | Path to requirements file (empty to skip) |
| `test-command` | string | `"pytest --showlocals -rA"` | Test command (empty to skip tests) |
| `lint-command` | string | `"ruff check ."` | Lint command (empty to skip lint) |
| `format-check-command` | string | `"ruff format --check ."` | Format check command (empty to skip) |

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

Runs `go build`, `go test`, and `go vet`.

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `go-version` | string | `"stable"` | Go version |

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
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@main
    secrets: inherit
```

#### Rust deb build with native deps:
```yaml
jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@main
    with:
      build-deps: "libdbus-1-dev libasound2-dev"
    secrets: inherit
```

#### Rust binary releases (no deb):
```yaml
jobs:
  build-release:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-exes.yml@main
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
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-ci.yml@main
```

#### Rust CI for embedded (custom target):
```yaml
jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-ci.yml@main
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
    uses: charlieh0tel/deb-workflows/.github/workflows/python-ci.yml@main
```

#### Python CI (lint only, no tests):
```yaml
jobs:
  ci:
    uses: charlieh0tel/deb-workflows/.github/workflows/python-ci.yml@main
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
    uses: charlieh0tel/deb-workflows/.github/workflows/go-ci.yml@main
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
    uses: charlieh0tel/deb-workflows/.github/workflows/dpkg-build-deb.yml@main
    with:
      before-build-hook: debchange --controlmaint --local="+ci${{ github.run_id }}~git$(git rev-parse --short HEAD)" "CI build"
    secrets: inherit
```

#### amd64-only deb (e.g. for an x86 server):
```yaml
jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@main
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
