#!/usr/bin/env python3
"""
xdsl_ccpp write_init_files sweep script (Stage 8a deferred validation).

Runs xdsl_ccpp's --emit-resolved-vars CLI against each of
test_write_init_files.py's fixtures, feeds the resulting JSON through
XdslCcppResolvedVars, calls write_init_files(), and compares the output
against the existing capgen-v1 golden files in sample_files/write_init_files/.

This is the deferred Stage 8a verification from capgen_v1_parity_backlog.md.
The 13-fixture "12/13 byte-identical" result was validated in that sandbox;
this script makes that check repeatable and permanent here.

Usage:
    python run_xdsl_ccpp_sweep.py [-v]

The -v flag prints a diff for each FAIL instead of just reporting the name.
"""

import argparse
import filecmp
import glob
import logging
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Path setup (mirrors test_write_init_files.py exactly)
# ---------------------------------------------------------------------------
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_CAM_ROOT = os.path.abspath(os.path.join(_TEST_DIR, os.pardir, os.pardir, os.pardir))
_CCPP_DIR = os.path.join(_CAM_ROOT, "ccpp_framework", "scripts")
_REGISTRY_DIR = os.path.join(_CAM_ROOT, "src", "data")
_SAMPLES_DIR = os.path.join(_TEST_DIR, "sample_files", "write_init_files")
_PRE_TMP_DIR = os.path.join(_TEST_DIR, "tmp")
_TMP_DIR = os.path.join(_PRE_TMP_DIR, "xdsl_sweep")
_SRC_MOD_DIR = os.path.join(_PRE_TMP_DIR, "SourceMods")
_INC_SEARCH_DIRS = [_SRC_MOD_DIR, _REGISTRY_DIR]

for _d in [_PRE_TMP_DIR, _TMP_DIR, _SRC_MOD_DIR]:
    os.makedirs(_d, exist_ok=True)

if not os.path.exists(_CCPP_DIR):
    sys.exit(f"ERROR: ccpp_framework/scripts not found at {_CCPP_DIR!r}.\n"
             "Ensure the ccpp_framework symlink is set up (see HANDOFF.md §2).")

sys.path.insert(0, _CCPP_DIR)
sys.path.insert(0, _REGISTRY_DIR)

# pylint: disable=wrong-import-position
from generate_registry_data import gen_registry
import write_init_files as write_init
from resolved_var_xdsl_ccpp import XdslCcppResolvedVars
# pylint: enable=wrong-import-position

# ---------------------------------------------------------------------------
# Fixture table
# Each entry: (label, reg_xml, out_source_name, extra_host_metas,
#              scheme_meta, sdf, datatable_name, vic_golden, pi_golden,
#              use_ic_names, use_constituents, use_vars_init_value)
#
# extra_host_metas: host meta files OTHER than simple_host.meta/host_var_host.meta
#   (the registry-generated .meta is always appended automatically).
# use_ic_names / use_constituents / use_vars_init_value: whether to pass the
#   gen_registry() return values at positions 2/3/4 to write_init_files().
#   Matches exactly how each test in test_write_init_files.py calls gen_registry().
# ---------------------------------------------------------------------------
_FIXTURES = [
    # label, reg_xml, out_source_name,
    # [primary host metas], scheme_meta, sdf, datatable,
    # vic_golden, pi_golden,
    # use_ic_names, use_constituents, use_vars_init_value
    ("simple",
     "simple_reg.xml", "physics_types_simple",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml", "datatable_simple.xml",
     "phys_vars_init_check_simple.F90", "physics_inputs_simple.F90",
     False, False, False),

    ("cnst",
     "simple_reg.xml", "physics_types_simple",
     ["simple_host.meta"], "temp_adjust_cnst.meta", "suite_simple.xml", "datatable_cnst.xml",
     "phys_vars_init_check_cnst.F90", "physics_inputs_cnst.F90",
     True, True, False),

    ("initial_value",
     "simple_reg_initial_value.xml", "physics_types_simple_initial_value",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml", "datatable_initial_value.xml",
     "phys_vars_init_check_initial_value.F90", "physics_inputs_initial_value.F90",
     True, False, True),

    ("noreq",
     "no_req_var_reg.xml", "physics_types_no_req_var",
     ["simple_host.meta"], "temp_adjust_noreq.meta", "suite_simple.xml",
     "datatable_no_req_var.xml",
     "phys_vars_init_check_noreq.F90", "physics_inputs_noreq.F90",
     False, False, False),

    ("protect",
     "protected_reg.xml", "physics_types_protected",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_protected.xml",
     "phys_vars_init_check_protect.F90", "physics_inputs_protect.F90",
     False, False, False),

    ("host_var",
     "host_var_reg.xml", "physics_types_host_var",
     ["host_var_host.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_host_var.xml",
     "phys_vars_init_check_host_var.F90", "physics_inputs_host_var.F90",
     False, False, False),

    ("no_horiz",
     "no_horiz_dim_reg.xml", "physics_types_no_horiz",
     ["simple_host.meta"], "temp_adjust_no_horiz.meta", "suite_simple.xml",
     "datatable_no_horiz.xml",
     "phys_vars_init_check_no_horiz.F90", "physics_inputs_no_horiz.F90",
     False, False, False),

    ("scalar",
     "scalar_var_reg.xml", "physics_types_scalar_var",
     ["simple_host.meta"], "temp_adjust_scalar.meta", "suite_simple.xml",
     "datatable_scalar.xml",
     "phys_vars_init_check_scalar.F90", "physics_inputs_scalar.F90",
     False, False, False),

    ("4D",
     "var_4D_reg.xml", "physics_types_4D",
     ["simple_host.meta"], "temp_adjust_4D.meta", "suite_simple.xml",
     "datatable_4D.xml",
     "phys_vars_init_check_4D.F90", "physics_inputs_4D.F90",
     False, False, False),

    ("ddt",
     "ddt_reg.xml", "physics_types_ddt",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_ddt.xml",
     "phys_vars_init_check_ddt.F90", "physics_inputs_ddt.F90",
     False, False, False),

    ("ddt2",
     "ddt2_reg.xml", "physics_types_ddt2",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_ddt2.xml",
     "phys_vars_init_check_ddt2.F90", "physics_inputs_ddt2.F90",
     False, False, False),

    ("ddt_array",
     "ddt_array_reg.xml", "physics_types_ddt_array",
     ["simple_host.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_ddt_array.xml",
     "phys_vars_init_check_ddt_array.F90", "physics_inputs_ddt_array.F90",
     True, False, False),

    ("param",
     "param_reg.xml", "physics_types_param",
     ["simple_host.meta"], "temp_adjust_param.meta", "suite_simple.xml",
     "datatable_param.xml",
     "phys_vars_init_check_param.F90", "physics_inputs_param.F90",
     False, False, False),

    ("constituent_dim",
     "simple_reg_constituent_dim.xml", "physics_types_simple_constituent_dim",
     ["simple_host.meta"], "temp_adjust_constituent_dim.meta", "suite_simple.xml",
     "datatable_constituent_dim.xml",
     "phys_vars_init_check_constituent_dim.F90", "physics_inputs_constituent_dim.F90",
     True, True, True),

    # meta_file: uses ref_theta.meta as an extra host file -- not in the
    # original 13 but included here since the plumbing now supports it.
    ("mf",
     "mf_reg.xml", "physics_types_mf",
     ["simple_host.meta", "ref_theta.meta"], "temp_adjust.meta", "suite_simple.xml",
     "datatable_mf.xml",
     "phys_vars_init_check_mf.F90", "physics_inputs_mf.F90",
     False, False, False),
]


def _s(path):
    """Absolute path within the samples directory."""
    return os.path.join(_SAMPLES_DIR, path)


def _t(path):
    """Absolute path within the sweep tmp directory."""
    return os.path.join(_TMP_DIR, path)


def _find_file(filename, search_dirs):
    for sdir in search_dirs:
        test_path = os.path.join(sdir, filename)
        if os.path.exists(test_path):
            return test_path
    return None


def run_fixture(label, reg_xml, out_source_name, extra_host_metas,
                scheme_meta, sdf, datatable_name,
                vic_golden, pi_golden,
                use_ic_names, use_constituents, use_vars_init_value,
                verbose=False):
    """Run one fixture through the full xdsl_ccpp pipeline.

    Returns (passed_vic, passed_pi, error_msg).
    passed_* is True for byte-identical, False for diff, None if xdsl_ccpp failed.
    """
    logger = logging.getLogger(f"sweep.{label}")

    out_meta = _t(out_source_name + ".meta")
    host_files = [_s(h) for h in extra_host_metas] + [out_meta]
    cap_datafile = _t(datatable_name)
    resolved_vars_json = _t(f"resolved_vars_{label}.json")
    xdsl_tmp = _t(f"xdsl_tmp_{label}")
    vic_out = _t(vic_golden)
    pi_out = _t(pi_golden)

    # Clean slate for this fixture's outputs
    for path in [out_meta, cap_datafile, resolved_vars_json, vic_out, pi_out]:
        if os.path.exists(path):
            os.remove(path)
    if os.path.isdir(xdsl_tmp):
        shutil.rmtree(xdsl_tmp)
    os.makedirs(xdsl_tmp, exist_ok=True)

    # Step 1: generate registry .meta file (exact same call as the test uses)
    reg_result = gen_registry(
        _s(reg_xml), "se", _TMP_DIR, 3,
        _SRC_MOD_DIR, _CAM_ROOT,
        loglevel=logging.ERROR,
        error_on_no_validate=True,
    )
    # reg_result is (ret_files, source_files, ic_names, constituents, vars_init_value)
    ic_names = reg_result[2] if use_ic_names else {}
    constituents = reg_result[3] if use_constituents else []
    vars_init_value = reg_result[4] if use_vars_init_value else []

    if not os.path.exists(out_meta):
        return None, None, f"gen_registry() did not produce {out_meta}"

    # Step 2: run xdsl_ccpp CLI
    cmd = [
        sys.executable, "-m", "xdsl_ccpp.tools.ccpp_dsl",
        "--host-files", ",".join(host_files),
        "--scheme-files", _s(scheme_meta),
        "--suites", _s(sdf),
        "--host-name", "cam",
        "-o", xdsl_tmp,
        "--tempdir", os.path.join(xdsl_tmp, "tmp"),
        "--emit-datatable", cap_datafile,
        "--emit-resolved-vars", resolved_vars_json,
        "--legacy-mode",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None, None, (
            f"xdsl_ccpp CLI failed (exit {result.returncode}):\n{result.stderr}"
        )

    if not os.path.exists(resolved_vars_json):
        return None, None, f"xdsl_ccpp produced no resolved_vars JSON at {resolved_vars_json}"

    # Step 3: load JSON through XdslCcppResolvedVars and run write_init_files
    resolved_vars = XdslCcppResolvedVars(resolved_vars_json)
    retmsg = write_init.write_init_files(
        resolved_vars, ic_names, constituents, vars_init_value,
        _TMP_DIR, _find_file, _INC_SEARCH_DIRS, 3, logger,
        phys_check_filename=vic_golden,
        phys_input_filename=pi_golden,
    )
    if retmsg:
        return None, None, f"write_init_files() returned error: {retmsg}"

    # Step 4: compare against golden files
    vic_golden_path = _s(vic_golden)
    pi_golden_path = _s(pi_golden)

    passed_vic = filecmp.cmp(vic_out, vic_golden_path, shallow=False)
    passed_pi = filecmp.cmp(pi_out, pi_golden_path, shallow=False)

    if verbose and not passed_vic:
        print(f"    DIFF {vic_golden}:")
        subprocess.run(["diff", vic_golden_path, vic_out], check=False)
    if verbose and not passed_pi:
        print(f"    DIFF {pi_golden}:")
        subprocess.run(["diff", pi_golden_path, pi_out], check=False)

    return passed_vic, passed_pi, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print diffs for failing fixtures")
    args = parser.parse_args()

    # Clear sweep tmp dir at start
    for f in glob.iglob(os.path.join(_TMP_DIR, "*")):
        if os.path.isfile(f):
            os.remove(f)

    print(f"Running xdsl_ccpp write_init_files sweep ({len(_FIXTURES)} fixtures)...\n")

    results = []
    for fixture in _FIXTURES:
        label = fixture[0]
        print(f"  {label:<20}", end="", flush=True)
        try:
            passed_vic, passed_pi, err = run_fixture(*fixture, verbose=args.verbose)
        except Exception as exc:  # pylint: disable=broad-except
            passed_vic, passed_pi, err = None, None, str(exc)

        if err:
            print(f"ERROR: {err}")
            results.append((label, "error"))
        else:
            vic_mark = "OK" if passed_vic else "DIFF"
            pi_mark = "OK" if passed_pi else "DIFF"
            overall = "PASS" if (passed_vic and passed_pi) else "FAIL"
            print(f"{overall}  (vic={vic_mark}, pi={pi_mark})")
            results.append((label, overall))

    # Summary
    passed = sum(1 for _, r in results if r == "PASS")
    failed = sum(1 for _, r in results if r == "FAIL")
    errors = sum(1 for _, r in results if r == "error")
    total = len(results)

    print(f"\nResults: {passed}/{total} PASS", end="")
    if failed:
        print(f", {failed} FAIL", end="")
    if errors:
        print(f", {errors} ERROR", end="")
    print()

    if failed or errors:
        print("\nFailed/errored fixtures:")
        for label, res in results:
            if res != "PASS":
                print(f"  {label}: {res}")
        sys.exit(1)


if __name__ == "__main__":
    main()
