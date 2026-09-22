# CI and release practices

Rules for the repositories that call these workflows. Each rule states what to
do and why. Where a rule exists because something broke, the failure is named.

Read this before changing a workflow, cutting a release, or setting up
publishing. When a rule and a repository disagree, fix the repository or change
the rule here; do not leave them disagreeing.

Governing rule: a check that cannot fail meaningfully is worse than no check.
It costs minutes, teaches people to ignore red, and hides the checks that do
mean something.


## 1. Shared workflows

Call a reusable workflow for anything more than three steps. Duplicated CI
drifts, and drift is invisible until one repository fails differently.

Pin call sites to the major tag: `@v1`. It moves with each release, so fixes
arrive without editing every caller.

Ship breaking changes as `v2`. Moving `v1` to a change that removes an input,
or that reddens a caller who changed nothing, breaks repositories silently.

A reusable workflow runs in the caller's checkout. It cannot read its own
repository's files. To load a composite action from this repository, check this
repository out into the caller's workspace and load it from there.

Anything checked out into the caller's workspace is visible to their tools. A
caller running `ruff check .` lints it. Hide it with a nested `.gitignore`
containing `*`, and keep the files clean anyway.

Why: `tests/inline-steps/test.py` was added here, and every python-ci caller
went red on lint and format without changing a line.

A re-run does not re-resolve a moving tag. It repeats the run with the same
resolved SHAs. To pick up a moved `v1`, push a new commit.

Do not declare `permissions:` on a job inside a reusable workflow unless every
caller must grant it. The caller's token cannot be widened, only narrowed.

Duplication that cannot be factored out needs a test that the copies match. See
`tests/inline-steps/test.py`.


## 2. Pinning

Pin every third-party `uses:` to a full commit SHA, with the version in a
trailing comment:

    - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1

Why: a tag can be moved to point at anything. A SHA cannot.

Pin the steps that hold a token first. A step handed a cross-repository PAT is
the one worth protecting.

Pair every pin with Dependabot. A pin with nothing to move it is a pin that
goes stale:

    # .github/dependabot.yml
    version: 2
    updates:
    - package-ecosystem: github-actions
      directory: /
      schedule:
        interval: weekly
      groups:
        actions:
          patterns: ["*"]

Check what the ref carried before pinning it. `dtolnay/rust-toolchain@stable`
took the channel from the branch name; the pinned action requires
`toolchain:` to be named.

Pin tool versions, not only actions. `npm install -g npm@latest` installed npm
12, which requires Node 22, into a workflow pinned to Node 20. Pin the range
you support: `npm@^11.5.1`.


## 3. Permissions and secrets

Grant `contents: write` on the job that needs it, never at workflow level.
Workflow level gives it to every job in the file, including pull request runs.

Do not use `secrets: inherit`. It passes every secret in the repository. Name
the secrets a workflow needs, or pass none: `GITHUB_TOKEN` is always available
to a called workflow.

Prefer `GITHUB_TOKEN` to a PAT. A PAT that can write to another repository is
readable by everyone with push access to this one, which is usually a wider
set of people than can write to the target.

Trigger another repository with `workflow_dispatch`, not
`repository_dispatch`. A fine-grained token needs Contents: write for
`repository_dispatch`, which lets the holder push commits -- including to the
workflow that runs with the signing key. `workflow_dispatch` needs Actions:
write, which starts runs and changes no code. Scope the token to the one
repository it triggers.

Never put a publishing credential in a page. Every page published under one
`github.io` account shares an origin, and therefore shares `localStorage`.

GitHub Pages is public even when served from a private repository. Do not
publish anything that names private repositories, their branches, or their
failures.

Delete a credential once nothing reads it. Proving the new path works is not
the same as removing the old one.


## 4. Rust toolchains

Pin the toolchain in `rust-toolchain.toml`. Leave the workflow's `toolchain`
input empty; it reads the channel from that file.

Do not name the version at the call site as well. Two places, no check that
they agree, and a mismatch costs a second toolchain download.

A job that installs the toolchain itself must name a channel: a SHA-pinned
`dtolnay/rust-toolchain` cannot read `rust-toolchain.toml`, and without a
`toolchain:` input it fails. Name it there, keep it equal to the file, or
convert the job to a `rust-ci.yml` call, which reads the file for you. The
rule above is about call sites, not about steps that have no choice.

Use `cargo +<toolchain> fmt` when the formatting toolchain differs from the
build toolchain. A `rust-toolchain.toml` outranks whatever the job installed,
so a bare `cargo fmt` silently runs the pinned one.

Expect the resolver to hold fixes back. It prefers versions compatible with
the pinned toolchain, so `cargo update -p <crate>` can stop short of the fixed
version. Use `--precise` when it does.


## 5. Dependencies and advisories

Run `cargo audit` (Rust), `govulncheck` (Go), or `pip-audit` (Python) in CI.
Fail the job on a finding. A warning nobody must act on is ignored.

Gate releases on the audit, not just pull requests. A tag whose dependencies
carry an advisory should build and publish nothing.

Enable Dependabot alerts and security updates on every repository. They are
off by default, which is how four repositories here accumulated advisories
published months earlier.

Know what each tool cannot see:

- `cargo audit` reads RustSec only. Advisories filed as GHSA alone are
  invisible to it.
- OSV carries RustSec and GHSA, but has no concept of a yanked version.
- Neither reports an unmaintained crate as a vulnerability. That is correct.

Treat findings by kind. A vulnerability blocks a release. Unmaintained and
unsound advisories are warnings. A yanked version still builds from a
lockfile, but nobody resolving afresh can select it, so move off it.

Expect fixes Dependabot cannot make. When the fixed version is a major bump of
a transitive dependency, the parent must move first: `reqwest` 0.11 to 0.12
cleared four advisories that no `cargo update` could reach.

Sometimes the fix is removal. `scc` had no fix in its 2.x line; updating
`serial_test` dropped the dependency entirely.

Accept what has no fix. `paste` is unmaintained with no successor in its
dependency chain. Record the decision; do not keep rediscovering it.


## 6. Releases

Bump the version, land it on a green default branch, then tag. The tag is the
release.

Run the documented pre-release checks, and make CI run them too. `cargo clippy`
without `--workspace` lints the default package only; a lint sat unseen in a
workspace member here until a release check found it by hand.

Never re-tag something that published. Recreate a tag only when nothing
consumed it: no registry version, no release, no downstream fetch.

Remember that merged is not shipped. A fixed branch with a vulnerable release
still exposes everyone who installs it. Cut the tag.

Do not document a step nobody runs. `RELEASING.md` told readers to
`cargo publish` a crate that had never existed on crates.io.


## 7. Trusted publishing

Publish through OIDC. The registry trusts a repository and a workflow file,
and mints a token for the run. Nothing long-lived is stored, so nothing can
leak or need rotating.

Request `id-token: write` on the publishing job alone.

crates.io, in the publishing job:

    - uses: rust-lang/crates-io-auth-action@c6f97d42243bad5fab37ca0427f495c86d5b1a18  # v1.0.5
      id: auth
    - run: cargo publish
      env:
        CARGO_REGISTRY_TOKEN: ${{ steps.auth.outputs.token }}

npm: remove `NODE_AUTH_TOKEN`, keep `--provenance`, and ensure npm is 11.5.1
or newer.

Configure the registry side before the next tag. The workflow cannot do it:

- crates.io: crate settings, Trusted Publishing, owner, repository, workflow
  filename, environment empty.
- npm: package settings, Trusted publisher, owner, repository, workflow
  filename. Tick "allow npm publish" unless you want staged releases that a
  maintainer promotes by hand.

Check the workflow filename. A single wrong letter (`build-dep.yml` for
`build-deb.yml`) fails the run, loudly and harmlessly.

Size confirmation windows for an eventually consistent registry. npm took five
minutes to serve a published version; a 50 second check failed a release that
had succeeded.

Delete the registry token after a real release proves the path.


## 8. Workflow design

Give each check its own job. Parallel jobs mean an advisory cannot hide a test
failure, and the job name says what broke.

Keep monitoring out of pipelines that hold signing keys. A red run should mean
one thing.

Make red mean act now. A failure older than the last push describes code that
is gone. A tag-only workflow that failed months ago is not today's problem.

Run `apt-get update` before `apt-get install`. Without it the runner installs
against the image's baked index, and a superseded package 404s.

Schedule off the hour, and know the limits: scheduled workflows queue behind
everyone else's on the hour, and GitHub disables them after 60 days of
repository inactivity.


## 9. Cross-repository visibility

Track what no single repository can show: CI across the fleet, and the gap
between a fixed branch and a vulnerable published release.

Build such a page statically. A browser calling an API is capped at 60
requests an hour unauthenticated, and a page that needs a token is a page that
leaks one.

Show staleness. A board that stops updating must say so rather than look
current.

Say what the view cannot see. This one reads OSV, so it misses yanked
versions; `cargo audit` sees those.


## 10. Working practice

Change by pull request, even alone. The diff is the review, and the body is
where the reasoning survives.

Write commit messages that explain why, with the evidence: the error, the
version, the run. Future readers cannot see the terminal.

Verify locally before tagging, and say plainly what you could not verify.
"`cargo check` passes for these crates; `dynarmic-sys` needs cmake and boost,
so CI is the real check" is useful. Silence is not.


## Checklists

### Adding CI to a repository

1. Add `.github/workflows/ci.yml` calling the shared workflow at `@v1`.
2. Pass `build-deps` for anything the build links against.
3. Pass `check-args: "--workspace --all-targets"` so clippy sees every member
   and every target.
4. Leave `toolchain` empty if `rust-toolchain.toml` exists.
5. Add `.github/dependabot.yml`.
6. Enable Dependabot alerts and security updates.
7. Expect the first run to fail. It is the first time these checks have run.

### Cutting a release

1. Confirm the default branch is green.
2. Bump the version; refresh the lockfile.
3. Run the pre-release checks: format, clippy, tests, audit.
4. Commit, push, wait for CI.
5. Tag `vX.Y.Z` and push the tag.
6. Confirm the release, its artifacts, and the registry version.

### Setting up trusted publishing

1. Add the publish job, gated on the build job and on the tag ref.
2. Request `id-token: write` on that job only.
3. Configure the registry: owner, repository, workflow filename.
4. Re-read the workflow filename.
5. Tag one package and watch it publish.
6. Delete the old registry token.
