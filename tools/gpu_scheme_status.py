#!/usr/bin/env python3
"""Write a table of which cam4/cam5/cam7 physics schemes run on the GPU,
verified bit-for-bit (GPU_SCHEME_STATUS.md at the repository root).

One row per scheme in src/physics/ncar_ccpp/suites/suite_cam{4,5,7}.xml, one
column per configuration:
  ✅  GPU-enabled and verified bit-for-bit on the GPU
  ❌  CPU only
  (blank) the scheme is not in that configuration's suite
  🧪  (after the mark, with --capture-root) a unit test is available: a
      capture replay driver was built for the scheme
      (<capture root>/capture_*/build*/test_<scheme>, from
      xdsl_ccpp --capture-scheme and build_capture_tests.sh) whose run phase
      was not left out (test_<scheme>.skipped)

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

The table has three sections, each headed by its count of ✅ schemes per
configuration (e.g. 47/132): per-timestep physics schemes (with libraries: a
register/init/final-only scheme whose module holds routines other schemes
call, e.g. wv_saturation); other schemes with only register/init/final
phases; history-diagnostics schemes (name containing
"diagnostics", whatever their phases).

Example (the GPU regression on Derecho):
  tools/gpu_scheme_status.py \\
    --test-root /glade/derecho/scratch/$USER/fphys_xdsl_test --test-id xdsl84gpu \\
    --capture-root /glade/derecho/scratch/$USER

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
OK, NO, TEST = "✅", "❌", "🧪"
PHASES = ("register", "init", "timestep_init", "run", "timestep_final", "final")
ONE_TIME = {"register", "init", "final"}

_SUB = (r"^[ \t]*(?:(?:pure|elemental|impure|recursive|module)[ \t]+)*"
        r"subroutine[ \t]+{}_(" + "|".join(PHASES) + r")\b")
_END = re.compile(r"^\s*end\s+subroutine", re.M | re.I)
_ACC = re.compile(r"^\s*!\$acc\b", re.M | re.I)
_PROC = re.compile(
    r"^[ \t]*(?:(?:pure|elemental|impure|recursive|module)[ \t]+)*"
    r"(?:(?:real|integer|logical|character|complex)(?:\([^)]*\))?[ \t]+)?"
    r"(?:subroutine|function)[ \t]+(\w+)", re.M | re.I)
_PHASE_PROC = re.compile(r"_(?:" + "|".join(PHASES) + r")$", re.I)
_MODULE = re.compile(r"^\s*module\s+(?!procedure\b)(\w+)", re.M | re.I)


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


def _library_users(path, texts):
    """Files that use the module in *path* and call one of its procedures
    other than scheme phases (<x>_init, <x>_run, ...)."""
    text = texts[path]
    module = _MODULE.search(text)
    procs = {p.lower() for p in _PROC.findall(text) if not _PHASE_PROC.search(p)}
    if module is None or not procs:
        return []
    use = re.compile(rf"^\s*use\s+{re.escape(module.group(1))}\b", re.M | re.I)
    called = re.compile(r"\b(?:" + "|".join(map(re.escape, sorted(procs))) + r")\b", re.I)
    return [other for other, other_text in texts.items()
            if other != path and use.search(other_text) and called.search(other_text)]


def scheme_sources(names):
    """name -> (phases, has_acc, source files, library) from the non-test
    Fortran. library: a scheme with only register/init/final phases whose
    module holds routines other schemes call (wv_saturation's qsat_vect,
    gw_common's gw_drag_prof): it does per-timestep work inside those
    schemes, so it counts as a physics scheme, and its OpenACC check covers
    the whole module."""
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
        library = False
        if phases and not phases - ONE_TIME:
            paths = [p for p in texts if os.path.basename(p) in sources]
            if any(_library_users(p, texts) for p in paths):
                library = True
                acc = any(_ACC.search(texts[p]) for p in paths)
        info[name] = (phases, acc, sources, library)
    return info


def _run_phase_left_out(capture_dir, scheme):
    """True when the generator left the scheme's run phase out of its
    replay driver: test_<scheme>.skipped lists "<scheme>_run: ..." (e.g.
    rrtmgp_pre_run, whose RRTMGP flux-object arguments the capture cannot
    record). Such a driver replays only the other phases, so it does not
    count as a unit test of the scheme."""
    path = os.path.join(capture_dir, f"test_{scheme}.skipped")
    if not os.path.isfile(path):
        return False
    with open(path) as skipped:
        return any(line.startswith(f"{scheme}_run:") for line in skipped)


def unit_tested(capture_root):
    """Schemes with a built capture replay test: an executable
    capture_*/build*/test_<scheme> under capture_root."""
    if capture_root is None:
        return set()
    found = set()
    for path in glob.glob(os.path.join(capture_root, "capture_*", "build*", "test_*")):
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            continue
        scheme = os.path.basename(path)[len("test_"):]
        if not _run_phase_left_out(os.path.dirname(os.path.dirname(path)), scheme):
            found.add(scheme)
    if not found:
        print(f"warning: no capture replay tests under {capture_root}", file=sys.stderr)
    return found


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
    parser.add_argument("--capture-root",
                        help="directory holding the capture_* replay directories; "
                             f"marks schemes with a built unit test {TEST}")
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
    tested_units = unit_tested(args.capture_root)

    sections = {"physics": [], "one_time": [], "diagnostics": []}
    counts = {sec: {c: [0, 0] for c in CONFIGS} for sec in sections}
    for name in names:
        phases, _acc, _sources, library = info[name]
        if "diagnostics" in name:
            section = "diagnostics"
        elif not phases - ONE_TIME and not library:
            section = "one_time"
        else:
            section = "physics"
        phases, acc, sources, library = info[name]
        built = bool(sources) and all(os.path.splitext(s)[0] in gpu_objs for s in sources)
        ok = name in tested and (name in callee_gpu or (acc and built))
        cells = []
        for config in CONFIGS:
            if name in suites[config]:
                cells.append((OK if ok else NO) + (f" {TEST}" if name in tested_units else ""))
                counts[section][config][0 if ok else 1] += 1
            else:
                cells.append("")
        mark = " ¹" if name in callee_gpu and ok else ""
        sections[section].append(f"| `{name}`{mark} | " + " | ".join(cells) + " |")

    def header(title, section):
        cells = " | ".join(f"**{counts[section][c][0]}/{sum(counts[section][c])}**"
                           for c in CONFIGS)
        return f"| **{title}** ({OK} / schemes) | {cells} |"

    table = "\n".join(
        [header("Physics schemes", "physics")] + sections["physics"]
        + [header("Register/init/final-only schemes", "one_time")] + sections["one_time"]
        + [header("Diagnostics schemes", "diagnostics")] + sections["diagnostics"]
    )
    totals = ", ".join(
        f"{c} {sum(counts[sec][c][0] for sec in sections)}/"
        f"{sum(sum(counts[sec][c]) for sec in sections)}" for c in CONFIGS
    )
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
{f"- {TEST} a unit test is available (a built capture replay of the scheme)" + chr(10) if tested_units else ""}
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
""" + table + f"""

¹ No OpenACC in the CCPP wrapper itself; the package it calls runs on the GPU
and is verified bit-for-bit.

## Sections

- **Physics schemes**: schemes with per-timestep phases (timestep_init, run,
  timestep_final), and libraries: register/init/final-only schemes whose
  module holds routines other schemes call each timestep
  (`wv_saturation`'s `qsat_vect`, `gravity_wave_drag_common`'s
  `gw_drag_prof`) -- the GPU porting work.
- **Register/init/final-only schemes**: no per-timestep work; {NO} here rarely
  needs a port.
- **Diagnostics schemes**: write history output on the host.
"""
    with open(args.output, "w") as out:
        out.write(text)
    print(f"{args.output}: {totals}")


if __name__ == "__main__":
    main()
