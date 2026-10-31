#!/usr/bin/env python3
"""Test the steps that are inlined into several jobs.

A reusable workflow runs in the caller's checkout, so it cannot source a script
or a composite action from this repo without checking this repo out too. A few
steps are therefore copy-pasted across jobs, and copies drift. This pulls each
step's shell back out of the workflow files -- never a copy of it -- and checks
that every copy is identical.

It also runs the toolchain resolver against fixture rust-toolchain.toml files,
which the reusable-workflow self-tests cannot do: they run against this repo's
own tree, which has no such file. Likewise the pre-release tag check, which the
self-tests never reach because they do not push tags.
"""

import pathlib
import subprocess
import sys
import tempfile

import yaml

WORKFLOWS = [
    "rust-ci.yml",
    "rust-build-deb.yml",
    "rust-build-exes.yml",
    "dpkg-build-deb.yml",
]

# step id -> how many jobs are expected to carry a copy of it
INLINED = {"rust-toolchain": 5, "cargo-audit": 3, "prerelease-tag": 3}

# (name, rust-toolchain.toml contents or None, toolchain input, expected)
RESOLVE_CASES = [
    ("no file", None, "", "stable"),
    ("no file, explicit input", None, "nightly", "nightly"),
    (
        "pinned",
        '[toolchain]\nchannel = "1.98.1"\ncomponents = ["clippy"]\n',
        "",
        "1.98.1",
    ),
    (
        "input overrides the file",
        '[toolchain]\nchannel = "1.98.1"\n',
        "1.90.0",
        "1.90.0",
    ),
    ("no spaces", '[toolchain]\nchannel="nightly"\n', "", "nightly"),
    (
        "dated nightly, indented, trailing comment",
        '[toolchain]\n  channel = "nightly-2025-01-01"  # for -Z flags\n',
        "",
        "nightly-2025-01-01",
    ),
    (
        "commented-out channel is ignored",
        '# channel = "beta"\n[toolchain]\nchannel = "stable"\n',
        "",
        "stable",
    ),
    # A toolchain pinned by path has no channel to install; stable is as good a
    # guess as any, and rustup still honours the file when cargo runs.
    ("path pin falls back", '[toolchain]\npath = "/opt/rust"\n', "", "stable"),
]

# (tag, expected prerelease output, or None when the check must fail)
PRERELEASE_CASES = [
    ("v1.2.0", "false"),
    ("v1.2.0-beta.1", "true"),
    ("v1.2.0-rc1", "true"),
    ("v1.2.0-alpha.2.3", "true"),
    # cargo-deb leaves these alone, so Debian sorts them after v1.2.0.
    ("v1.2.0-beta", None),
    ("v1.2.0-1", None),
    ("v1.2.0-", None),
]


def copies(root, step_id):
    """Every copy of a step's shell, keyed by where it came from."""
    found = {}
    for name in WORKFLOWS:
        workflow = yaml.safe_load((root / ".github/workflows" / name).read_text())
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                if step.get("id") == step_id:
                    found[f"{name}:{job_name}"] = step["run"]
    return found


def check_identical(root, step_id, expected_count):
    found = copies(root, step_id)
    if len(found) != expected_count:
        sys.exit(
            f"expected '{step_id}' in {expected_count} jobs, found {sorted(found)}"
        )
    canonical, script = min(found.items())
    for where, other in sorted(found.items()):
        if other != script:
            sys.exit(f"{where} has drifted from {canonical}; keep the copies identical")
    print(f"ok   {expected_count} identical copies of '{step_id}'")
    return script


def run_step(script, env, files=None):
    """Run a step's shell in a scratch directory; its outputs, or None if it failed."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        for name, contents in (files or {}).items():
            (tmp / name).write_text(contents)
        out = tmp / "github_output"
        out.touch()
        result = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", script],
            cwd=tmp,
            env={"PATH": "/usr/bin:/bin", "GITHUB_OUTPUT": str(out), **env},
            check=False,
            stdout=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return None
        return dict(line.split("=", 1) for line in out.read_text().splitlines())


def resolve(script, toml, toolchain):
    files = {} if toml is None else {"rust-toolchain.toml": toml}
    values = run_step(script, {"TOOLCHAIN": toolchain}, files)
    if values is None:
        sys.exit(f"resolver failed: TOOLCHAIN={toolchain!r}")
    return values["toolchain"]


def check_prerelease(script, tag):
    values = run_step(script, {"TAG": tag})
    return None if values is None else values["prerelease"]


def main():
    root = pathlib.Path(__file__).resolve().parents[2]
    scripts = {step: check_identical(root, step, n) for step, n in INLINED.items()}

    failures = 0
    for name, toml, toolchain, want in RESOLVE_CASES:
        got = resolve(scripts["rust-toolchain"], toml, toolchain)
        if got != want:
            failures += 1
            print(f"FAIL {name}: TOOLCHAIN={toolchain!r} -> {got!r}, want {want!r}")
        else:
            print(f"ok   {name}: {got}")
    for tag, want in PRERELEASE_CASES:
        got = check_prerelease(scripts["prerelease-tag"], tag)
        if got != want:
            failures += 1
            print(f"FAIL {tag}: prerelease -> {got!r}, want {want!r}")
        else:
            print(f"ok   {tag}: {'refused' if got is None else got}")
    if failures:
        sys.exit(f"{failures} case(s) failed")
    print(
        f"\n{len(RESOLVE_CASES)} resolver and "
        f"{len(PRERELEASE_CASES)} pre-release cases passed"
    )


if __name__ == "__main__":
    main()
