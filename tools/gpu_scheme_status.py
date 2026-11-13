#!/usr/bin/env python3
"""Write a table of which cam4/cam5/cam7 physics schemes run on the GPU,
verified bit-for-bit (GPU_SCHEME_STATUS.md at the repository root).

One row per scheme in src/physics/ncar_ccpp/suites/suite_cam{4,5,7}.xml, one
column per configuration:
  ✅  GPU-enabled and verified bit-for-bit on the GPU
  ❌  CPU only
  (blank) the scheme is not in that configuration's suite

A scheme is ✅ when all of these hold:
  * its own <scheme>_<phase> routines carry OpenACC directives (any !$acc
    directive: a scheme with only data directives drives kernels in routines
    it calls, e.g. tropopause_find, the RRTMGP gas-optics/RTE schemes), or it
    is named with --callee-gpu (its GPU work is all in a package it calls,
    e.g. micro_pumas_ccpp -> PUMAS);
  * every source file defining it is compiled with OpenACC: its object is in
    the GPU object lists of ccs_config/machines/Depends.nvhpc (PUMAS_OBJS
    through GPU_SCHEME_OBJS);
  * it runs in a GPU test that passed BASELINE, i.e. matched its CPU
    baseline bit-for-bit (a GPU regression with compare=<tag>): a GPU case
    (*_gpu.*.<test id>) in --test-root whose TestStatus has "PASS ...
    BASELINE" contributes the suites of its CAM_CONFIG_OPTS
    (--physics-suites); or it is named with --verified-scheme (verified some
    other way, e.g. a capture replay).

Verification is per scheme: a scheme verified in any suite is ✅ in every
configuration that uses it. The tool cannot tell whether a scheme's source
changed after the test run; give it the latest regression.

Example (the GPU regression on Derecho):
  tools/gpu_scheme_status.py \\
    --test-root /glade/derecho/scratch/$USER/fphys_xdsl_test --test-id xdsl84gpu

Reads files only; it builds and runs nothing.
"""

import argparse
import datetime
import glob
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHYSICS = os.path.join(REPO, "src", "physics", "ncar_ccpp")
DEPENDS = os.path.join(REPO, "ccs_config", "machines", "Depends.nvhpc")
CONFIGS = ("cam4", "cam5", "cam7")
OK, NO = "✅", "❌"
PHASES = ("register", "init", "timestep_init", "run", "timestep_final", "final")
ONE_TIME = {"register", "init", "final"}

_SUB = (r"^[ \t]*(?:(?:pure|elemental|impure|recursive|module)[ \t]+)*"
        r"subroutine[ \t]+{}_(" + "|".join(PHASES) + r")\b")
_END = re.compile(r"^\s*end\s+subroutine", re.M | re.I)
_ACC = re.compile(r"^\s*!\$acc\b", re.M | re.I)


def suite_schemes(path):
    """The schemes of a suite file, in order, each once."""
    names = []
    for elem in ET.parse(path).iter("scheme"):
        name = elem.text.strip()
        if name not in names:
            names.append(name)
    return names


def suite_file(suite):
    for sub in ("suites", os.path.join("test", "test_suites")):
        path = os.path.join(PHYSICS, sub, f"suite_{suite}.xml")
        if os.path.isfile(path):
            return path
    return None


def gpu_objects():
    """Object names compiled with OpenACC: those listed in Depends.nvhpc
    from PUMAS_OBJS up to the GPU_OBJS definition."""
    text = open(DEPENDS).read()
    start, end = text.find("PUMAS_OBJS="), text.find("GPU_OBJS :=")
    if start < 0 or end < 0:
        sys.exit(f"{DEPENDS}: PUMAS_OBJS= / GPU_OBJS := not found; update gpu_objects()")
    return set(re.findall(r"([A-Za-z0-9_]+)\.o\b", text[start:end]))


def case_suites(case_dir):
    """--physics-suites of a case (env_build.xml CAM_CONFIG_OPTS)."""
    path = os.path.join(case_dir, "env_build.xml")
    if not os.path.isfile(path):
        return []
    for entry in ET.parse(path).iter("entry"):
        if entry.get("id") == "CAM_CONFIG_OPTS":
            match = re.search(r"--physics-suites[ =]+(\S+)", entry.get("value", ""))
            return match.group(1).split(",") if match else []
    return []


def verified_suites(test_root, test_ids):
    """Suites of the GPU cases that passed BASELINE, and the cases used."""
    suites, cases = set(), []
    for test_id in test_ids:
        found = False
        for case_dir in sorted(glob.glob(os.path.join(test_root, f"*_gpu.*.{test_id}"))):
            status = os.path.join(case_dir, "TestStatus")
            if not os.path.isfile(status):
                continue
            found = True
            if any(line.startswith("PASS ") and " BASELINE" in line
                   for line in open(status)):
                suites.update(case_suites(case_dir))
                cases.append(os.path.basename(case_dir))
        if not found:
            print(f"warning: no GPU cases with a TestStatus for test id {test_id} "
                  f"in {test_root}", file=sys.stderr)
    return suites, cases


def scheme_sources(names):
    """name -> (phases, has_acc, source files) from the non-test Fortran."""
    files = [f for f in glob.glob(os.path.join(PHYSICS, "**", "*.F90"), recursive=True)
             if f"{os.sep}test{os.sep}" not in f]
    texts = {f: open(f, errors="replace").read() for f in files}
    info = {}
    for name in names:
        pattern = re.compile(_SUB.format(re.escape(name)), re.M | re.I)
        phases, acc, sources = set(), False, set()
        for path, text in texts.items():
            for match in pattern.finditer(text):
                phases.add(match.group(1).lower())
                sources.add(os.path.basename(path))
                end = _END.search(text, match.end())
                body = text[match.end(): end.start() if end else len(text)]
                acc = acc or bool(_ACC.search(body))
        info[name] = (phases, acc, sources)
    return info


def git_head(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--test-root", required=True,
                        help="directory holding the GPU regression's case directories")
    parser.add_argument("--test-id", action="append", required=True,
                        help="test id of a GPU regression run with compare= (repeatable)")
    parser.add_argument("--verified-scheme", action="append", default=[],
                        help="scheme verified bit-for-bit on the GPU outside those runs "
                             "(repeatable)")
    parser.add_argument("--callee-gpu", action="append", default=None,
                        help="scheme whose GPU work is all in a package it calls "
                             "(repeatable; default: micro_pumas_ccpp)")
    parser.add_argument("-o", "--output", default=os.path.join(REPO, "GPU_SCHEME_STATUS.md"),
                        help="output file (default: %(default)s)")
    args = parser.parse_args()
    callee_gpu = set(args.callee_gpu if args.callee_gpu is not None else ["micro_pumas_ccpp"])

    suites = {c: suite_schemes(os.path.join(PHYSICS, "suites", f"suite_{c}.xml"))
              for c in CONFIGS}
    tested_suites, cases = verified_suites(args.test_root, args.test_id)
    if not cases:
        sys.exit("no GPU case passed BASELINE; nothing counts as verified")
    tested = set()
    for suite in sorted(tested_suites):
        path = suite_file(suite)
        if path is None:
            print(f"warning: suite {suite} (from a test case) has no suite file",
                  file=sys.stderr)
            continue
        tested.update(suite_schemes(path))
    tested.update(args.verified_scheme)

    names = sorted({n for schemes in suites.values() for n in schemes}, key=str.lower)
    info = scheme_sources(names)
    gpu_objs = gpu_objects()

    rows, init_only, diagnostics = [], [], []
    counts = {c: [0, 0] for c in CONFIGS}
    for name in names:
        phases, acc, sources = info[name]
        built = bool(sources) and all(os.path.splitext(s)[0] in gpu_objs for s in sources)
        ok = name in tested and (name in callee_gpu or (acc and built))
        cells = []
        for config in CONFIGS:
            if name in suites[config]:
                cells.append(OK if ok else NO)
                counts[config][0 if ok else 1] += 1
            else:
                cells.append("")
        mark = " ¹" if name in callee_gpu and ok else ""
        rows.append(f"| `{name}`{mark} | " + " | ".join(cells) + " |")
        if not ok:
            if not phases - ONE_TIME:
                init_only.append(name)
            elif "diagnostics" in name:
                diagnostics.append(name)

    totals = " · ".join(f"{c}: {counts[c][0]} {OK} / {counts[c][1]} {NO} of {sum(counts[c])}"
                        for c in CONFIGS)
    evidence = ", ".join(args.test_id)
    if args.verified_scheme:
        evidence += "; also verified elsewhere: " + ", ".join(
            f"`{s}`" for s in sorted(args.verified_scheme))
    callee_note = ", ".join(f"`{s}`" for s in sorted(callee_gpu))

    text = f"""# GPU status of the CAM physics schemes

Which schemes in the cam4, cam5 and cam7 suites
(`src/physics/ncar_ccpp/suites/suite_cam{{4,5,7}}.xml`) run on the GPU and are
confirmed bit-for-bit against the nvhpc CPU build.

- {OK} GPU-enabled and verified bit-for-bit on the GPU
- {NO} CPU only
- blank: the scheme is not in that configuration's suite

**Totals:** {totals}

Generated {datetime.date.today().isoformat()} by `tools/gpu_scheme_status.py`
(CAM-SIMA `{git_head(REPO)}`, atmospheric_physics `{git_head(PHYSICS)}`) from GPU
tests that passed bit-for-bit against their CPU baselines: {evidence}
({len(cases)} cases). A scheme is {OK} when its own routines carry OpenACC
directives (or, for {callee_note}, the package it calls runs on the GPU), its
object is compiled with OpenACC (`ccs_config/machines/Depends.nvhpc`), and it
runs in one of those tests. Verification is per scheme, so a scheme verified in
one suite is {OK} in every configuration that uses it; cam5 and cam7 marks can
come from the cam4 and FPHYStest runs.

| Scheme | cam4 | cam5 | cam7 |
|---|:---:|:---:|:---:|
""" + "\n".join(rows) + f"""

¹ No OpenACC in the CCPP wrapper itself; the package it calls runs on the GPU
and is verified bit-for-bit.

## Notes on the {NO} entries

Not every {NO} needs a GPU port:
- **Init/register/final only** ({len(init_only)}): no per-timestep work.
  {", ".join(f"`{n}`" for n in init_only)}.
- **History diagnostics** ({len(diagnostics)}): write history output on the host.
  {", ".join(f"`{n}`" for n in diagnostics)}.
"""
    with open(args.output, "w") as out:
        out.write(text)
    print(f"{args.output}: {totals}")


if __name__ == "__main__":
    main()
