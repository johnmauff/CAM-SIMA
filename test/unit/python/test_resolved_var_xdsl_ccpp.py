"""
Python unit testing collection for resolved_var_xdsl_ccpp.py's
XdslCcppResolvedVars adapter -- translates xdsl_ccpp's own
--emit-resolved-vars JSON artifact into the backend-neutral ResolvedVar
records write_init_files.py consumes (see resolved_var.py).

Flagged by Copilot review (johnmauff/CAM-SIMA#2): this adapter had no
test coverage at all, unlike resolved_var_capgen_v1.py (covered throughout
test_write_init_files.py). These tests build the JSON directly (as a
temp file) rather than running the real xdsl_ccpp CLI, since they only
need to exercise this adapter's own translation logic -- not
re-verify xdsl_ccpp's own generator, which is xdsl-ccpp-fresh's own
test suite's job.

To run these unit tests, simply type:

python test_resolved_var_xdsl_ccpp.py

or (for more verbose output):

python test_resolved_var_xdsl_ccpp.py -v
"""

#----------------------------------------
#Import required python libraries/modules:
#----------------------------------------
import json
import os
import os.path
import sys
import tempfile
import unittest

#Add directory to python path:
CURRDIR = os.path.abspath(os.path.dirname(__file__))
CAM_ROOT_DIR = os.path.join(CURRDIR, os.pardir, os.pardir, os.pardir)
REG_GEN_DIR = os.path.abspath(os.path.join(CAM_ROOT_DIR, "src", "data"))

#Add "src/data" directory to python path (resolved_var.py and
#resolved_var_xdsl_ccpp.py both live there):
sys.path.append(REG_GEN_DIR)

# pylint: disable=wrong-import-position
from resolved_var_xdsl_ccpp import XdslCcppResolvedVars
# pylint: enable=wrong-import-position


def _write_json(data):
    """Write <data> to a temp JSON file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as file_:
        json.dump(data, file_)
    return path


###############################################################################
class ResolvedVarXdslCcppTest(unittest.TestCase):
###############################################################################
    """Tests for XdslCcppResolvedVars."""

    def setUp(self):
        """Track temp files created by each test for cleanup."""
        self._tmp_paths = []

    def tearDown(self):
        for path in self._tmp_paths:
            if os.path.exists(path):
                os.remove(path)
            # end if
        # end for

    def _adapter_for(self, data):
        path = _write_json(data)
        self._tmp_paths.append(path)
        return XdslCcppResolvedVars(path)

    #-------------------------------------
    #Per-phase conversion tests
    #-------------------------------------

    def test_per_phase_conversion_basic_fields(self):
        """A plain, non-DDT record's fields should carry through unchanged."""
        data = {
            "phases": {
                "run": [
                    {
                        "standard_name": "eastward_wind",
                        "intent": "inout",
                        "is_advected": True,
                        "is_constituent": False,
                        "is_protected": False,
                        "is_optional": False,
                        "is_host_table_var": False,
                        "model_var_name": "u_wind",
                        "model_module_name": "physics_types",
                        "import_name": "u_wind",
                        "call_expr": "u_wind",
                        "array_ref_dims": [],
                        "dim_names": ["horizontal_dimension", "vertical_layer_dimension"],
                    },
                ],
            },
            "host_vars": {},
        }
        adapter = self._adapter_for(data)
        records = adapter.call_list("run")
        self.assertEqual(len(records), 1)
        var = records[0]
        self.assertEqual(var.standard_name, "eastward_wind")
        self.assertEqual(var.intent, "inout")
        self.assertTrue(var.is_advected)
        self.assertFalse(var.is_constituent)
        self.assertEqual(var.local_name, "u_wind")
        self.assertEqual(var.host_module, "physics_types")
        self.assertEqual(var.dimensions, ["horizontal_dimension", "vertical_layer_dimension"])
        self.assertTrue(var.has_horizontal_dim)
        self.assertEqual(var.vertical_dim_name, "lev")

    def test_call_list_unknown_phase_returns_empty(self):
        adapter = self._adapter_for({"phases": {}, "host_vars": {}})
        self.assertEqual(adapter.call_list("finalize"), [])

    #-------------------------------------
    #Host-variable fallback tests
    #-------------------------------------

    def test_host_variable_fallback_resolves_name_not_in_any_phase(self):
        """A real host variable that's never itself a scheme argument (e.g.
        a DDT member's own array-section index variable) must still resolve
        via the top-level "host_vars" dict, not just the per-phase lists.
        """
        data = {
            "phases": {"run": []},
            "host_vars": {
                "index_of_potential_temperature": ["index_of_theta", "physics_types"],
            },
        }
        adapter = self._adapter_for(data)
        var = adapter.resolve_by_standard_name("index_of_potential_temperature")
        self.assertIsNotNone(var)
        self.assertEqual(var.local_name, "index_of_theta")
        self.assertEqual(var.host_module, "physics_types")
        self.assertEqual(var.intent, "in")

    def test_host_variable_fallback_missing_key_returns_none(self):
        data = {"phases": {}, "host_vars": {}}
        adapter = self._adapter_for(data)
        self.assertIsNone(adapter.resolve_by_standard_name("nonexistent_standard_name"))

    def test_per_phase_lookup_takes_priority_over_host_vars_fallback(self):
        """If a name is in both the per-phase call list and host_vars, the
        richer per-phase record must win, not the sparser host_vars entry.
        """
        data = {
            "phases": {
                "run": [
                    {
                        "standard_name": "shared_name",
                        "intent": "in",
                        "model_var_name": "from_call_list",
                        "import_name": "from_call_list",
                        "call_expr": "from_call_list",
                    },
                ],
            },
            "host_vars": {
                "shared_name": ["from_host_vars", "some_module"],
            },
        }
        adapter = self._adapter_for(data)
        var = adapter.resolve_by_standard_name("shared_name")
        self.assertEqual(var.local_name, "from_call_list")

    def test_absent_host_vars_key_degrades_cleanly(self):
        """An older xdsl_ccpp build's JSON predating the "host_vars" key
        must not raise -- resolve_by_standard_name should just fall back
        to the per-phase-only behavior.
        """
        data = {
            "phases": {
                "run": [
                    {"standard_name": "in_call_list", "intent": "in",
                     "model_var_name": "x"},
                ],
            },
        }
        adapter = self._adapter_for(data)
        self.assertIsNotNone(adapter.resolve_by_standard_name("in_call_list"))
        self.assertIsNone(adapter.resolve_by_standard_name("not_anywhere"))

    #-------------------------------------
    #DDT / import-field tests
    #-------------------------------------

    def test_ddt_member_import_name_and_call_expr_differ_from_local_name(self):
        """suite_cap.py's _apply_ddt_chain overwrites import_name/call_expr
        in place for a DDT member match -- import_name becomes the real
        instance variable, call_expr the full "%"-chain. local_name (the
        bare declared field name) must stay distinct from both.
        """
        data = {
            "phases": {
                "run": [
                    {
                        "standard_name": "potential_temperature",
                        "intent": "inout",
                        "model_var_name": "theta",
                        "model_module_name": "physics_types_ddt",
                        "import_name": "phys_state",
                        "call_expr": "phys_state%theta",
                        "array_ref_dims": [],
                    },
                ],
            },
            "host_vars": {},
        }
        adapter = self._adapter_for(data)
        var = adapter.call_list("run")[0]
        self.assertEqual(var.local_name, "theta")
        self.assertEqual(var.import_name, "phys_state")
        self.assertEqual(var.call_expr, "phys_state%theta")
        self.assertEqual(var.host_module, "physics_types_ddt")

    def test_non_ddt_import_name_and_call_expr_default_to_model_var_name(self):
        """For a non-DDT arg, suite_cap.py's own writer already sets
        import_name/call_expr equal to model_var_name -- this adapter must
        read them as given, not re-derive them, but the *result* for the
        ordinary case is still equal to model_var_name.
        """
        data = {
            "phases": {
                "run": [
                    {
                        "standard_name": "surface_pressure",
                        "intent": "in",
                        "model_var_name": "psfc",
                        "import_name": "psfc",
                        "call_expr": "psfc",
                    },
                ],
            },
            "host_vars": {},
        }
        adapter = self._adapter_for(data)
        var = adapter.call_list("run")[0]
        self.assertEqual(var.import_name, "psfc")
        self.assertEqual(var.call_expr, "psfc")

    #-------------------------------------
    #Absent optional key tests
    #-------------------------------------

    def test_minimal_record_missing_all_optional_keys(self):
        """Only standard_name is required by _to_resolved_var's own
        record["standard_name"] access; every other key must have a
        sensible default when absent, not raise KeyError.
        """
        data = {
            "phases": {
                "run": [
                    {"standard_name": "bare_minimum"},
                ],
            },
            "host_vars": {},
        }
        adapter = self._adapter_for(data)
        var = adapter.call_list("run")[0]
        self.assertEqual(var.standard_name, "bare_minimum")
        self.assertEqual(var.intent, "")
        self.assertFalse(var.is_protected)
        self.assertFalse(var.is_advected)
        self.assertFalse(var.is_constituent)
        self.assertFalse(var.is_host_table_var)
        self.assertFalse(var.is_optional)
        self.assertIsNone(var.host_module)
        self.assertIsNone(var.local_name)
        self.assertIsNone(var.import_name)
        self.assertIsNone(var.call_expr)
        self.assertEqual(var.dimensions, [])
        self.assertFalse(var.has_horizontal_dim)
        self.assertIsNone(var.vertical_dim_name)
        self.assertIsNone(var.array_ref_dims)
        self.assertIsNone(var.intrinsic_element_names)

    def test_empty_array_ref_dims_becomes_none_not_empty_list(self):
        """suite_cap.py's own base record always includes array_ref_dims
        as an empty list (only a real DDT-member subscript overwrites it
        with real content) -- this adapter normalizes the empty-list case
        to None, matching ResolvedVar's own "can't derive this, leave
        None" convention for a var with nothing to report.
        """
        data = {
            "phases": {
                "run": [
                    {"standard_name": "x", "intent": "in", "array_ref_dims": []},
                ],
            },
            "host_vars": {},
        }
        adapter = self._adapter_for(data)
        var = adapter.call_list("run")[0]
        self.assertIsNone(var.array_ref_dims)


#################################################
#Run the unit tests when this module is executed
#################################################
if __name__ == "__main__":
    unittest.main()
