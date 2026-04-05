# deb-workflows

Reusable GitHub Actions workflows for building Rust projects. Supports native builds on amd64 and arm64 (via GitHub's `ubuntu-22.04-arm` runners for Debian bookworm glibc compatibility) and Windows.

## Available Workflows

### `rust-build-deb.yml`

Builds `.deb` packages using `cargo-deb`. Creates a GitHub Release with `.deb` artifacts when a `v*` tag is pushed.

**Requirements:** The calling repo must have a `[package.metadata.deb]` section in `Cargo.toml`. See [cargo-deb documentation](https://github.com/kornelski/cargo-deb#readme).

**Default targets:** amd64 (`ubuntu-latest`) and arm64 (`ubuntu-22.04-arm`).

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install (e.g. `"libdbus-1-dev"`) |
| `targets` | string | (see below) | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 |

**Default targets JSON:**
```json
[
  {"target": "x86_64-unknown-linux-gnu", "os": "ubuntu-latest", "arch": "amd64"},
  {"target": "aarch64-unknown-linux-gnu", "os": "ubuntu-22.04-arm", "arch": "arm64"}
]
```

### `rust-build-exes.yml`

Builds release binaries for Linux and Windows. Creates a GitHub Release with binary artifacts when a `v*` tag is pushed. No `.deb` packaging.

**Default targets:** amd64 Linux (`ubuntu-latest`), arm64 Linux (`ubuntu-22.04-arm`), and x86_64 Windows (`windows-latest`).

**Inputs:**

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `build-deps` | string | `""` | Space-separated apt packages to install on Linux |
| `targets` | string | (see below) | JSON array of build targets |
| `run-tests` | boolean | `true` | Run `cargo test` on amd64 Linux |

**Default targets JSON:**
```json
[
  {"target": "x86_64-unknown-linux-gnu", "os": "ubuntu-latest", "arch": "amd64"},
  {"target": "aarch64-unknown-linux-gnu", "os": "ubuntu-22.04-arm", "arch": "arm64"},
  {"target": "x86_64-pc-windows-msvc", "os": "windows-latest", "arch": "amd64"}
]
```

## How to Adopt

### Step 1: Choose a workflow

- Use `rust-build-deb.yml` if you want `.deb` packages (requires `[package.metadata.deb]` in `Cargo.toml`).
- Use `rust-build-exes.yml` if you just want release binaries.

### Step 2: Create the caller workflow

Create `.github/workflows/build.yml` (or similar) in your repo:

#### Minimal example (deb, no native deps):
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

#### With build dependencies:
```yaml
jobs:
  build-deb:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-deb.yml@main
    with:
      build-deps: "libdbus-1-dev libasound2-dev"
    secrets: inherit
```

#### Binary releases (no deb):
```yaml
jobs:
  build-release:
    uses: charlieh0tel/deb-workflows/.github/workflows/rust-build-exes.yml@main
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

### Step 3: Required caller workflow fields

Every caller workflow **must** include:
- `permissions: contents: write` at the top level (needed for the release job to create GitHub Releases).
- `secrets: inherit` on the job (passes `GITHUB_TOKEN` to the reusable workflow).

### Step 4: For deb builds, add cargo-deb metadata

Add a `[package.metadata.deb]` section to your `Cargo.toml`:

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

The workflow will build for all targets and create a GitHub Release with the artifacts.

## Target matrix format

Each entry in the `targets` JSON array must have:

| Field | Description |
|-------|-------------|
| `target` | Rust target triple (e.g. `x86_64-unknown-linux-gnu`) |
| `os` | GitHub runner (e.g. `ubuntu-latest`, `ubuntu-22.04-arm`, `windows-latest`) |
| `arch` | Architecture label for artifact naming (e.g. `amd64`, `arm64`) |

## Notes

- arm64 Linux builds use `ubuntu-22.04-arm` (native arm64 runner) for Debian bookworm glibc compatibility (glibc 2.35).
- amd64 Linux builds use `ubuntu-latest`.
- Cargo registry, git index, and build artifacts are cached.
- Tests only run on amd64 Linux by default.

## License

MIT
