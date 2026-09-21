#!/usr/bin/env python3
"""Test the inlined "Resolve Rust toolchain" step.

The step is copy-pasted into every Rust job, because a reusable workflow runs in
the caller's checkout and cannot source a script from this repo. The reusable-
workflow self-tests can't reach its interesting branch either: they run against
this repo's own tree, which has no rust-toolchain.toml.

So this pulls the shell out of the workflow files themselves -- never a copy of
it -- checks that every copy is identical, and runs it against fixture toolchain
files.
"""

import pathlib
import subprocess
import sys
import tempfile

import yaml

WORKFLOWS = ["rust-ci.yml", "rust-build-deb.yml", "rust-build-exes.yml"]
STEP_ID = "rust-toolchain"

# (name, rust-toolchain.toml contents or None, toolchain input, expected)
CASES = [
    ("no file", None, "", "stable"),
    ("no file, explicit input", None, "nightly", "nightly"),
    ("pinned", '[toolchain]\nchannel = "1.98.1"\ncomponents = ["clippy"]\n', "", "1.98.1"),
    ("input overrides the file", '[toolchain]\nchannel = "1.98.1"\n', "1.90.0", "1.90.0"),
    ("no spaces", '[toolchain]\nchannel="nightly"\n', "", "nightly"),
    ("dated nightly, indented, trailing comment",
     '[toolchain]\n  channel = "nightly-2025-01-01"  # for -Z flags\n', "", "nightly-2025-01-01"),
    ("commented-out channel is ignored",
     '# channel = "beta"\n[toolchain]\nchannel = "stable"\n', "", "stable"),
    # A toolchain pinned by path has no channel to install; stable is as good a
    # guess as any, and rustup still honours the file when cargo runs.
    ("path pin falls back", '[toolchain]\npath = "/opt/rust"\n', "", "stable"),
]


def scripts(root):
    """Every copy of the resolve step's shell, keyed by where it came from."""
    found = {}
    for name in WORKFLOWS:
        workflow = yaml.safe_load((root / ".github/workflows" / name).read_text())
        for job_name, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                if step.get("id") == STEP_ID:
                    found[f"{name}:{job_name}"] = step["run"]
    return found


def run(script, toml, toolchain):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        if toml is not None:
            (tmp / "rust-toolchain.toml").write_text(toml)
        out = tmp / "github_output"
        out.touch()
        subprocess.run(
            ["bash", "-eo", "pipefail", "-c", script],
            cwd=tmp,
            env={"PATH": "/usr/bin:/bin", "TOOLCHAIN": toolchain, "GITHUB_OUTPUT": str(out)},
            check=True,
            stdout=subprocess.DEVNULL,
        )
        values = dict(line.split("=", 1) for line in out.read_text().splitlines())
        return values["toolchain"]


def main():
    root = pathlib.Path(__file__).resolve().parents[2]
    found = scripts(root)
    if len(found) != 5:
        sys.exit(f"expected the resolve step in 5 jobs, found {sorted(found)}")

    canonical, script = sorted(found.items())[0]
    for where, other in sorted(found.items()):
        if other != script:
            sys.exit(f"{where} has drifted from {canonical}; keep the copies identical")

    failures = 0
    for name, toml, toolchain, want in CASES:
        got = run(script, toml, toolchain)
        if got != want:
            failures += 1
            print(f"FAIL {name}: TOOLCHAIN={toolchain!r} -> {got!r}, want {want!r}")
        else:
            print(f"ok   {name}: {got}")
    if failures:
        sys.exit(f"{failures} case(s) failed")
    print(f"\n{len(CASES)} cases passed against {len(found)} identical copies of the step")


if __name__ == "__main__":
    main()
