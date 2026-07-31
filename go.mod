// Root module so `go build ./...` (as go-ci.yml runs it) finds the fixture
// under tests/go, mirroring the root Cargo.toml that serves the Rust fixtures.
module github.com/charlieh0tel/deb-workflows

go 1.22
