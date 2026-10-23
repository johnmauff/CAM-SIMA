"""
Python unit testing collection for the various
cam_autogen.py functions, including their
error-handling processes.  Please note that
these tests will only work with Python 3.7
or later.

To run these unit tests, simply type:

python test_cam_autogen.py

or (for more verbose output):

python test_cam_autogen.py -v

which will currently run 15 tests, all of which should pass.
"""

#----------------------------------------
#Import required python libraries/modules:
#----------------------------------------
import os
import os.path
import sys
import shutil
import glob
import filecmp
from collections.abc import Iterable

#Python unit-testing library:
import unittest

#Add directory to python path:
_CURRDIR = os.path.abspath(os.path.dirname(__file__))
_CAM_ROOT_DIR = os.path.join(_CURRDIR, os.pardir, os.pardir, os.pardir)
_CAM_CONF_DIR = os.path.abspath(os.path.join(_CAM_ROOT_DIR, "cime_config"))
_CCPP_DIR = os.path.join(_CAM_ROOT_DIR, "ccpp_framework", "scripts")

#Check for all necessary directories:
if not os.path.exists(_CAM_CONF_DIR):
    _EMSG = f"ERROR: Cannot find required '{_CAM_CONF_DIR}' directory"
    raise ImportError(_EMSG)
#End if
if not os.path.exists(_CCPP_DIR):
    _EMSG = f"ERROR: Cannot find CCPP-framework routines in '{_CCPP_DIR}'"
    raise ImportError(_EMSG)
#End if

#Add "cime_config" directory to python path:
sys.path.append(_CAM_CONF_DIR)

#Add "ccpp_framework" directory to python path:
sys.path.append(_CCPP_DIR)

#Import CAM autogen functions:
# pylint: disable=wrong-import-position
from cam_autogen import CamAutoGenError
from cam_autogen import _update_file, _find_schemes_in_sdf
from cam_autogen import _find_metadata_files, generate_registry
from cam_autogen import generate_physics_suites, generate_init_routines
from cam_autogen import _find_suite_file, _find_schemes_in_py_suite
from cam_autogen import _python_suite_inputs

#Import necessary CCPP framework functions:
from parse_tools import read_xml_file
from metadata_table import find_scheme_names

# pylint: enable=wrong-import-position

#+++++++++++++++++++++++++++++++++++++++++++
#Create "fake" CIME case to test cam_autogen
#+++++++++++++++++++++++++++++++++++++++++++

class FakeBuildCache:

    """
    Fake BuildCache class with methods
    needed to properly test cam_autogen
    functions.
    """

    # pylint: disable=unused-argument
    # pylint: disable=no-self-use
    def __init__(self):
        pass

    def update_registry(self, gen_reg_file, registry_files,
                        dycore):

        """Fake version of 'update_regsitry' method"""

    def registry_mismatch(self, gen_reg_file, registry_files,
                          dycore):

        """
        Fake version of 'registry_mismatch' method.
        It always return False, in order to avoid running the
        actual generation routines when performing doctests.
        """
        return False

    def update_ccpp(self, sdfs, scheme_files, host_files, xml_files,
                    namelist_meta_files, namelist_groups, create_nl_file,
                    preproc_defs, kind_phys, ccpp_generator="capgen"):

        """Fake version of 'update_ccpp' method"""

    def ccpp_mismatch(self, sdfs, scheme_files, host_files,
                      preproc_defs, kind_phys, ccpp_generator="capgen"):

        """
        Fake version of 'ccpp_mismatch' method.
        It always return False, in order to avoid running the
        actual generation routines when performing doctests.
        """
        return False

    def xml_nl_mismatch(self, create_nl_file, xml_files):

        """
        Fake version of 'xml_nl_mismatch' method.
        It always return False, in order to avoid running the
        actual generation routines when performing doctests.
        """
        return False

    def update_init_gen(self, input_file):

        """Fake version of 'update_init_gen' method."""

    def init_write_mismatch(self, input_file):

        """
        Fake version of 'init_write_mismatch' method.
        It always return False, in order to avoid running the
        actual generation routines when performing doctests.
        """
        return False

    def reg_file_list(self):

        """Fake version of 'reg_file_list' property."""

        return []

    def scheme_nl_metadata(self):

        """Fake version of 'scheme_nl_metadata' property."""

        return []

    def scheme_nl_groups(self):

        """Fake version of 'scheme_nl_groups' property."""

        return []

    def ic_names(self):

        """Fake version of 'ic_names' property."""

        return {}

    def constituents(self):
        """Fake version of 'constituents' property."""
        return []

    def vars_init_value(self):
        """Fake version of 'vars_init_value' property."""
        return []

    # pylint: enable=no-self-use
    # pylint: enable=unused-argument

class RecordingBuildCache(FakeBuildCache):

    """FakeBuildCache that records the suite inputs passed to 'ccpp_mismatch'."""

    def __init__(self):
        super().__init__()
        self.suite_inputs = None

    def ccpp_mismatch(self, sdfs, scheme_files, host_files,
                      preproc_defs, kind_phys, ccpp_generator="capgen"):

        """Record <sdfs>, then behave like FakeBuildCache.ccpp_mismatch."""
        self.suite_inputs = list(sdfs)
        return False

# Stand-in for a Python suite script: prints suite IR the way
# xdsl_ccpp's export_suite does, without needing xdsl_ccpp installed.
_FAKE_PY_SUITE = """import sys
assert "--legacy-mode" in sys.argv
print('"ccpp.suite"() <{suite_name = "simple", version = "1.0"}> ({')
print('  "ccpp.scheme"() <{scheme_name = "temp_adjust"}> : () -> ()')
print('  "ccpp.scheme"() <{scheme_name = "other_scheme", arg_overrides = {x = "1"}}> : () -> ()')
print('  "ccpp.scheme"() <{scheme_name = "temp_adjust"}> : () -> ()')
print('}) : () -> ()')
"""

#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#Main cam_autogen testing routine, used when script is run directly
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class CamAutoGenTestRoutine(unittest.TestCase):

    """
    Runs all CAM code autogeneration (cam_autogen) tests,
    to ensure that the scripts and error-handling methods
    are running properly.
    """

    #Set-up unit tests:
    def setUp(self):

        """Initalize Config_CAM object being tested."""

        #create fake build cache:
        test_cache = FakeBuildCache()

        #Add CAM build cache object to unittest object list:
        self.test_cache = test_cache

        #Set needed paths:
        test_suite_path = os.path.join(_CURRDIR, "sample_files")

        test_tmp_dir = os.path.join(_CURRDIR, "tmp")
        test_bldroot = os.path.join(test_tmp_dir, "test_bldroot")
        test_reg_dir = os.path.join(test_bldroot, "cam_registry")
        test_src_mods_dir = os.path.join(test_tmp_dir, "SourceMods")

        # Does "tmp" directory exist?  If not then create it:
        if not os.path.exists(test_tmp_dir):
            os.mkdir(test_tmp_dir)
        #End if

        # Remove old test directories if they exist:
        if os.path.exists(test_bldroot):
            shutil.rmtree(test_bldroot)
        #End if

        # Create source code directories needed in order
        # to avoid running the actual code generators
        # while testing:
        os.mkdir(test_bldroot)
        os.mkdir(test_reg_dir)
        os.mkdir(os.path.join(test_bldroot, "ccpp"))
        os.mkdir(os.path.join(test_bldroot, "phys_init"))

        # Remove old test SourceMods test directory,
        # and crate a new empty directory:
        if os.path.exists(test_src_mods_dir):
            shutil.rmtree(test_src_mods_dir)
        #End if
        os.mkdir(test_src_mods_dir)

        # Add paths to self:
        self.test_suite_path   = test_suite_path
        self.test_bldroot      = test_bldroot
        self.test_reg_dir      = test_reg_dir
        self.test_src_mods_dir = test_src_mods_dir

        # Add generated fortran scoping indent value to self:
        self.fort_indent = 3

    #+++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "_update_file" autogen function
    #+++++++++++++++++++++++++++++++++++++++++++++++++

    def test_update_file_no_exist(self):

        """Check that "_update_file" correctly copies over a missing file."""

        #Set path to original file:
        orig_file = os.path.join(self.test_suite_path, "physics_types_simple.F90")

        #Set path to new (copied) file:
        new_file = os.path.join(self.test_bldroot, "physics_types_simple.F90")

        #Run function:
        _update_file("physics_types_simple.F90", orig_file, self.test_bldroot)

        #Check that the new file exists:
        self.assertTrue(os.path.exists(new_file))

        #Check that the new file matches the original:
        self.assertTrue(filecmp.cmp(new_file, orig_file, shallow=False))

        #Remove "new" file from bld directory:
        if os.path.exists(new_file):
            os.remove(new_file)
        #End if

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_update_file_match(self):

        """Check that "_update_file correctly does nothing if the two files match."""

        #Set path to original file:
        orig_file = os.path.join(self.test_suite_path, "physics_types_simple.F90")

        #Set path to new (copied) file:
        new_file = os.path.join(self.test_bldroot, "physics_types_simple.F90")

        #Copy over original file:
        shutil.copy2(orig_file, new_file)

        #Run function:
        _update_file("physics_types_simple.F90", orig_file, self.test_bldroot)

        #Check that the new file exists:
        self.assertTrue(os.path.exists(new_file))

        #Check that the new file matches the original:
        self.assertTrue(filecmp.cmp(new_file, orig_file, shallow=False))

        #Remove "new" file from bld directory:
        if os.path.exists(new_file):
            os.remove(new_file)
        #End if

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_update_file_mismatch(self):

        """Check that "_update_file" correctly replaces a mis-matched file."""

        #Set path to original file:
        orig_file = os.path.join(self.test_suite_path, "physics_types_simple.F90")

        #Set path to "bad" file:
        bad_file = os.path.join(self.test_suite_path, "physics_types_ddt2.F90")

        #Set path to new (copied) file:
        new_file = os.path.join(self.test_bldroot, "physics_types_simple.F90")

        #Copy over a different file but label it as the same file:
        shutil.copy2(bad_file, new_file)

        #Run function:
        _update_file("physics_types_simple.F90", orig_file, self.test_bldroot)

        #Check that the new file exists:
        self.assertTrue(os.path.exists(new_file))

        #Check that the new file matches the original:
        self.assertTrue(filecmp.cmp(new_file, orig_file, shallow=False))

        #Remove "new" file from bld directory:
        if os.path.exists(new_file):
            os.remove(new_file)
        #End if

    #+++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "_find_schemes_in_sdf" autogen function
    #+++++++++++++++++++++++++++++++++++++++++++++++++

    def test_find_schemes_in_sdf(self):

        """Check that "_find_schemes_in_sdf" correctly finds schemes in an SDF file."""

        #Set path to sample SDF file:
        test_sdf = os.path.join(self.test_suite_path, "write_init_files", "suite_simple.xml")

        #Open XML file:
        _, test_suite = read_xml_file(test_sdf)

        #Set expected results:
        expected_results = ["temp_adjust"]

        #Run function:
        gen_results = _find_schemes_in_sdf(test_suite)

        #Check that the output list matches what is expected:
        self.assertEqual(gen_results, expected_results)

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_find_schemes_no_schemes(self):

        """
        Check that "_find_schemes_in_sdf" correctly
        returns an empty list if no schemes are found.
        """

        #Set path to a non-SDF file:
        bad_sdf = os.path.join(self.test_suite_path, "banana_namelist.xml")

        #Open XML file:
        _, bad_file_root = read_xml_file(bad_sdf)

        #Run function:
        gen_results = _find_schemes_in_sdf(bad_file_root)

        #Check that the output list is empty:
        self.assertEqual(gen_results, [])

    #+++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "_find_metadata_files" autogen function
    #+++++++++++++++++++++++++++++++++++++++++++++++++

    def test_find_metadata_files(self):

        """Check that "_find_metadata_files" works properly if given the proper inputs."""

        #Copy test files into test SourceMods directory:
        test_meta = os.path.join(self.test_suite_path, "write_init_files", "temp_adjust.meta")
        test_src = os.path.join(self.test_suite_path, "write_init_files", "temp_adjust.F90")

        shutil.copy2(test_meta, self.test_src_mods_dir)
        shutil.copy2(test_src, self.test_src_mods_dir)

        #Set expected dictionary values:
        expected_schemes = {'temp_adjust': (f'{self.test_src_mods_dir}'+os.sep+'temp_adjust.meta',
                            f'{self.test_src_mods_dir}'+os.sep+'temp_adjust.F90', None)}

        #Run function:
        test_scheme_files = _find_metadata_files([self.test_src_mods_dir], find_scheme_names)

        #Check that the output dictionary matches what is expected:
        self.assertEqual(test_scheme_files, expected_schemes)

        #Remove test files:
        test_meta_files = glob.glob(f"{self.test_src_mods_dir}"+os.sep+"temp_adjust.*")
        for test_file in test_meta_files:
            os.remove(test_file)
        #End for

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_missing_src_files(self):

        """
        Check that "_find_metadata_files" raises the appropriate error
        if there are meta files with no equivalent source (Fortran) files.
        """

        #Copy test files into test SourceMods directory:
        phys_dup_file = os.path.join(self.test_suite_path, "phys_types_dup_section.meta")
        phys_no_table = os.path.join(self.test_suite_path, "phys_types_no_table.meta")
        phys_ref_pres = os.path.join(self.test_suite_path, "ref_pres.meta")

        shutil.copy2(phys_dup_file, self.test_src_mods_dir)
        shutil.copy2(phys_no_table, self.test_src_mods_dir)
        shutil.copy2(phys_ref_pres, self.test_src_mods_dir)

        #Set expected error message:
        emsg = "ERROR: No Fortran files were found for the following meta files:"
        emsg += f"\n{self.test_src_mods_dir}"+os.sep+"phys_types_dup_section.meta"
        emsg += f"\n{self.test_src_mods_dir}"+os.sep+"phys_types_no_table.meta"
        emsg += f"\n{self.test_src_mods_dir}"+os.sep+"ref_pres.meta"

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            #Run function:
            _ = _find_metadata_files([self.test_src_mods_dir], find_scheme_names)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

        #Remove test files:
        test_meta_files = glob.glob(f"{self.test_src_mods_dir}"+os.sep+"*.meta")
        for test_file in test_meta_files:
            os.remove(test_file)
        #End for

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_two_schemes_one_namelist_xml(self):

        """
        Check that "_find_metadata_files" raises the appropriate error
        if there is a namelist meta, source, and xml file, but the
        meta and source files contain multiple schemes.
        """

        #Copy files into test SourceMods directory:
        two_schemes_meta = os.path.join(self.test_suite_path, "autogen_files",
                                        "two_scheme_banana.meta")
        two_schemes_src = os.path.join(self.test_suite_path, "autogen_files",
                                       "two_scheme_banana.F90")
        two_schemes_xml = os.path.join(self.test_suite_path, "autogen_files",
                                       "two_scheme_banana_namelist.xml")

        shutil.copy2(two_schemes_meta, self.test_src_mods_dir)
        shutil.copy2(two_schemes_src, self.test_src_mods_dir)
        shutil.copy2(two_schemes_xml, self.test_src_mods_dir)

        #Set xml path used in expected error message:
        bad_xml_file = os.path.join(self.test_src_mods_dir, "two_scheme_banana_namelist.xml")

        #Set expected error message:
        emsg = "ERROR: This XML file was associated with more than one scheme"
        emsg += f"\n{bad_xml_file}"

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            #Run function:
            _ = _find_metadata_files([self.test_src_mods_dir], find_scheme_names)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

        #---------------------
        #Now try two XML files:
        #---------------------

        #Set xml path for second bad XML file:
        bad_xml_file_copy = os.path.join(self.test_src_mods_dir, "two_scheme_copy_namelist.xml")

        #Copy files into test SourceMods directory again:
        shutil.copy2(two_schemes_meta, os.path.join(self.test_src_mods_dir, "two_scheme_copy.meta"))
        shutil.copy2(two_schemes_src, os.path.join(self.test_src_mods_dir, "two_scheme_copy.F90"))
        shutil.copy2(two_schemes_xml, bad_xml_file_copy)

        #Set new expected error message:
        emsg = "ERROR: These XML files were associated with more than one scheme"
        emsg += f"\n{bad_xml_file}\n{bad_xml_file_copy}"

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            #Run function:
            _ = _find_metadata_files([self.test_src_mods_dir], find_scheme_names)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

        #Remove test files:
        test_meta_files = glob.glob(f"{self.test_src_mods_dir}"+os.sep+"two_scheme_banana*")
        for test_file in test_meta_files:
            os.remove(test_file)
        #End for

        test_meta_files = glob.glob(f"{self.test_src_mods_dir}"+os.sep+"two_scheme_copy*")
        for test_file in test_meta_files:
            os.remove(test_file)
        #End for

    #+++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "generate_registry" autogen function
    #+++++++++++++++++++++++++++++++++++++++++++++++++

    def test_generate_registry(self):

        """Check that "generate_registry" works properly if given the proper inputs."""

        #Set path to src/data (where the registry file is located):
        test_data_search = [os.path.join(_CAM_ROOT_DIR, "src", "data")]

        #Set expected output tuple:
        expected_results = (f'{self.test_bldroot}'+os.sep+'cam_registry', False, [], {}, [], [])

        #Run registry generation function:
        gen_results = generate_registry(test_data_search, self.test_cache, _CAM_ROOT_DIR,
                                        self.test_bldroot, self.test_src_mods_dir, 'se',
                                        self.fort_indent)

        #Check that the output tuple matches what is expected:
        self.assertEqual(gen_results, expected_results)

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_bad_generate_registry_search_path(self):

        """
        Check that "generate_registry" fails with the correct
        error if unable to find a registry file.
        """

        #Set "bad" path for testing:
        bad_path = ["/bad/path"]

        #Set expected error message:
        emsg = f"ERROR: Unable to find CAM registry, registry.xml, in [{bad_path[0]}]"

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            #Run function:
            _ = generate_registry(bad_path, self.test_cache, _CAM_ROOT_DIR,
                                  self.test_bldroot, self.test_src_mods_dir, 'se',
                                  self.fort_indent)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

    #++++++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "generate_physics_suites" autogen function
    #++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_generate_physics_suites(self):

        """Check that "generate_physics_suites" works properly if given the proper inputs"""

        #Copy test files into test SourceMods directory:
        test_suite = os.path.join(self.test_suite_path, "write_init_files", "suite_simple.xml")
        test_meta  = os.path.join(self.test_suite_path, "write_init_files", "temp_adjust.meta")
        test_src  = os.path.join(self.test_suite_path, "write_init_files", "temp_adjust.F90")

        shutil.copy2(test_suite, self.test_src_mods_dir)
        shutil.copy2(test_meta, self.test_src_mods_dir)
        shutil.copy2(test_src, self.test_src_mods_dir)

        #Set expected output tuple:
        expected_results = ([f'{self.test_bldroot}'+os.sep+'ccpp_physics',
                             f'{self.test_bldroot}'+os.sep+'ccpp'], False,
                             f'{self.test_bldroot}'+os.sep+'ccpp'+os.sep+'ccpp_datatable.xml',
                             [], None, {"temp_adjust"})

        #Run physics suite generation function:
        gen_results = generate_physics_suites(self.test_cache, "UNSET", "cam", "simple",
                                              _CAM_ROOT_DIR, self.test_bldroot,
                                              self.test_reg_dir, [],
                                              self.test_src_mods_dir, False, False)

        #Due to the presence of a "dict_values" dictview object which needs
        #to be treated in a special way, the tuples will need to be iterated
        #over and each element compared directly:
        for idx, elem in enumerate(gen_results):
            #Check if a variable is iterable.  If so then convert to a list,
            #which is needed to manage the "dict_values" view object:
            if isinstance(elem, Iterable):
                #Convert to list and then compare:
                self.assertEqual(list(elem), list(expected_results[idx]))
            else:
                #Assert elements match:
                self.assertEqual(elem, expected_results[idx])
            #End if
        #End for

        #Remove extra test files:
        test_meta_files = glob.glob(f"{self.test_src_mods_dir}"+os.sep+"temp_adjust.*")
        for test_file in test_meta_files:
            os.remove(test_file)
        #End for
        os.remove(os.path.join(self.test_src_mods_dir, "suite_simple.xml"))

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_missing_sdf_generate_physics_suites(self):

        """
        Check that "generate_physics_suites" fails with
        the correct error if the specified SDF cannot be
        found.
        """

        #Set expected error message:
        emsg = "ERROR: Unable to find SDF for suite 'missing'"

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            _ = generate_physics_suites(self.test_cache, "UNSET", "cam", "missing",
                                        _CAM_ROOT_DIR, self.test_bldroot,
                                        self.test_reg_dir, [],
                                        self.test_src_mods_dir, False, False)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

    #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_missing_scheme_generate_physics_suites(self):

        """
        Check that "generate_physics_suites" fails with
        the correct error if a scheme specified by an
        SDF cannot be found.
        """

        #Set expected error message:
        emsg = "ERROR: No metadata file found for physics scheme 'temp_adjust'"

        #Copy test files into test SourceMods directory:
        test_suite = os.path.join(self.test_suite_path, "write_init_files", "suite_simple.xml")
        shutil.copy2(test_suite, self.test_src_mods_dir)

        #Expect "CamAutoGenError":
        with self.assertRaises(CamAutoGenError) as autoerr:
            _ = generate_physics_suites(self.test_cache, "UNSET", "cam", "simple",
                                        _CAM_ROOT_DIR, self.test_bldroot,
                                        self.test_reg_dir, [],
                                        self.test_src_mods_dir, False, False)
        #End with

        #Check that error message matches what's expected:
        self.assertEqual(emsg, str(autoerr.exception))

        #Remove extra test file:
        os.remove(os.path.join(self.test_src_mods_dir, "suite_simple.xml"))

    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for Python suites (xdsl_ccpp's Python frontend)
    #++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _write_py_suite(self, directory, name="simple", content=_FAKE_PY_SUITE):

        """Write a stand-in Python suite 'suite_<name>.py' into <directory>."""

        path = os.path.join(directory, f"suite_{name}.py")
        with open(path, "w", encoding="utf-8") as suite_file:
            suite_file.write(content)
        #End with
        return path

    def _copy_temp_adjust_scheme(self):

        """Copy the temp_adjust test scheme into the test SourceMods directory."""

        for suffix in ("meta", "F90"):
            shutil.copy2(os.path.join(self.test_suite_path, "write_init_files",
                                      f"temp_adjust.{suffix}"), self.test_src_mods_dir)
        #End for

    def test_find_suite_file(self):

        """
        Check that "_find_suite_file" searches directories in order and,
        within one directory, prefers a Python suite over an SDF.
        """

        other_dir = os.path.join(self.test_bldroot, "other_suites")
        os.mkdir(other_dir)
        xml_path = os.path.join(self.test_src_mods_dir, "suite_simple.xml")
        shutil.copy2(os.path.join(self.test_suite_path, "write_init_files",
                                  "suite_simple.xml"), xml_path)
        later_py = self._write_py_suite(other_dir)

        #An SDF in an earlier directory wins over a Python suite in a later one:
        self.assertEqual(_find_suite_file("simple", [self.test_src_mods_dir, other_dir]),
                         xml_path)
        self.assertEqual(_find_suite_file("simple", [other_dir, self.test_src_mods_dir]),
                         later_py)

        #Within one directory, the Python suite wins:
        same_dir_py = self._write_py_suite(self.test_src_mods_dir)
        self.assertEqual(_find_suite_file("simple", [self.test_src_mods_dir]), same_dir_py)
        self.assertIsNone(_find_suite_file("missing", [self.test_src_mods_dir]))

        os.remove(xml_path)
        os.remove(same_dir_py)

    def test_find_schemes_in_py_suite(self):

        """
        Check that "_find_schemes_in_py_suite" returns the schemes a Python
        suite calls, in call order without duplicates.
        """

        suite_path = self._write_py_suite(self.test_src_mods_dir)
        self.assertEqual(_find_schemes_in_py_suite(suite_path, sys.executable),
                         ["temp_adjust", "other_scheme"])
        os.remove(suite_path)

    def test_py_suite_imports_from_library(self):

        """
        Check that a Python suite outside the suite library (suites-py) can
        import the library's modules, and that those modules, but not the
        library's own suites, are inputs of the suite.
        """

        library = os.path.join(self.test_bldroot, "library")
        os.makedirs(os.path.join(library, "parameterizations"))
        helper = os.path.join(library, "parameterizations", "helper.py")
        with open(helper, "w", encoding="utf-8") as helper_file:
            helper_file.write("SCHEMES = ['temp_adjust', 'other_scheme']\n")
        #End with
        self._write_py_suite(library, name="production")
        suite_path = self._write_py_suite(
            self.test_src_mods_dir,
            content="from parameterizations.helper import SCHEMES\n" + _FAKE_PY_SUITE)
        self.assertEqual(_find_schemes_in_py_suite(suite_path, sys.executable, library),
                         ["temp_adjust", "other_scheme"])
        with self.assertRaises(CamAutoGenError):
            _find_schemes_in_py_suite(suite_path, sys.executable)
        #End with
        self.assertEqual(_python_suite_inputs(suite_path, library), [suite_path, helper])
        os.remove(suite_path)
        shutil.rmtree(library)

    def test_failing_py_suite(self):

        """Check that a Python suite that fails to run raises CamAutoGenError."""

        suite_path = self._write_py_suite(self.test_src_mods_dir,
                                          content="raise SystemExit('broken suite')\n")
        with self.assertRaises(CamAutoGenError) as autoerr:
            _find_schemes_in_py_suite(suite_path, sys.executable)
        #End with
        self.assertIn("Unable to run Python suite", str(autoerr.exception))
        self.assertIn("broken suite", str(autoerr.exception))
        os.remove(suite_path)

    def test_generate_physics_suites_python_suite(self):

        """
        Check that "generate_physics_suites" accepts a Python suite under
        xdsl_ccpp: its schemes are found by running it, and the suite plus
        the Python modules beside it and in suites-py are the suite inputs given to the
        build cache.
        """

        self._copy_temp_adjust_scheme()
        other_scheme = os.path.join(self.test_src_mods_dir, "other_scheme")
        shutil.copy2(os.path.join(self.test_src_mods_dir, "temp_adjust.meta"),
                     other_scheme + ".meta")
        shutil.copy2(os.path.join(self.test_src_mods_dir, "temp_adjust.F90"),
                     other_scheme + ".F90")
        with open(other_scheme + ".meta", encoding="utf-8") as meta_file:
            meta_text = meta_file.read().replace("temp_adjust", "other_scheme")
        #End with
        with open(other_scheme + ".meta", "w", encoding="utf-8") as meta_file:
            meta_file.write(meta_text)
        #End with
        suite_path = self._write_py_suite(self.test_src_mods_dir)
        helper_path = os.path.join(self.test_src_mods_dir, "my_package.py")
        with open(helper_path, "w", encoding="utf-8") as helper_file:
            helper_file.write("# helper module imported by the suite\n")
        #End with

        cache = RecordingBuildCache()
        gen_results = generate_physics_suites(cache, "UNSET", "cam", "simple",
                                              _CAM_ROOT_DIR, self.test_bldroot,
                                              self.test_reg_dir, [],
                                              self.test_src_mods_dir, False, False,
                                              ccpp_generator="xdsl_ccpp")

        self.assertEqual(gen_results[5], {"temp_adjust", "other_scheme"})
        #The suite, the modules beside it, and those of the suite library
        #(suites-py), whose own suites are not inputs:
        self.assertEqual(cache.suite_inputs[0], suite_path)
        self.assertIn(helper_path, cache.suite_inputs)
        library = os.path.abspath(os.path.join(_CAM_ROOT_DIR, "src", "physics", "ncar_ccpp",
                                               "suites-py"))
        self.assertIn(os.path.join(library, "categories", "interface.py"), cache.suite_inputs)
        self.assertFalse([path for path in cache.suite_inputs[1:]
                          if os.path.basename(path).startswith("suite_")])

        for test_file in glob.glob(os.path.join(self.test_src_mods_dir, "*")):
            os.remove(test_file)
        #End for

    def test_python_suite_requires_xdsl_ccpp(self):

        """Check that a Python suite is rejected unless CCPP_GENERATOR=xdsl_ccpp."""

        suite_path = self._write_py_suite(self.test_src_mods_dir)
        with self.assertRaises(CamAutoGenError) as autoerr:
            _ = generate_physics_suites(self.test_cache, "UNSET", "cam", "simple",
                                        _CAM_ROOT_DIR, self.test_bldroot,
                                        self.test_reg_dir, [],
                                        self.test_src_mods_dir, False, False)
        #End with
        self.assertIn("requires CCPP_GENERATOR=xdsl_ccpp", str(autoerr.exception))
        os.remove(suite_path)

    def test_python_suite_must_be_only_suite(self):

        """Check that a Python suite cannot be combined with other suites."""

        self._copy_temp_adjust_scheme()
        suite_path = self._write_py_suite(self.test_src_mods_dir)
        shutil.copy2(os.path.join(self.test_suite_path, "write_init_files",
                                  "suite_simple.xml"),
                     os.path.join(self.test_src_mods_dir, "suite_other.xml"))
        with open(os.path.join(self.test_src_mods_dir, "temp_adjust.meta"),
                  encoding="utf-8") as meta_file:
            meta_text = meta_file.read().replace("temp_adjust", "other_scheme")
        #End with
        with open(os.path.join(self.test_src_mods_dir, "other_scheme.meta"), "w",
                  encoding="utf-8") as meta_file:
            meta_file.write(meta_text)
        #End with
        shutil.copy2(os.path.join(self.test_src_mods_dir, "temp_adjust.F90"),
                     os.path.join(self.test_src_mods_dir, "other_scheme.F90"))
        with self.assertRaises(CamAutoGenError) as autoerr:
            _ = generate_physics_suites(self.test_cache, "UNSET", "cam", "simple;other",
                                        _CAM_ROOT_DIR, self.test_bldroot,
                                        self.test_reg_dir, [],
                                        self.test_src_mods_dir, False, False,
                                        ccpp_generator="xdsl_ccpp")
        #End with
        self.assertIn("must be the only physics suite", str(autoerr.exception))
        for test_file in glob.glob(os.path.join(self.test_src_mods_dir, "*")):
            os.remove(test_file)
        #End for

    #+++++++++++++++++++++++++++++++++++++++++++++++++++
    #Tests for "generate_init_routines" autogen function
    #+++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_generate_init_routines(self):

        """Check that "test_generate_init_routines" works properly if given the proper inputs"""

        #Set expected output path:
        expected_path = os.path.join(self.test_bldroot, "phys_init")

        #Run init routines generation function:
        gen_path = generate_init_routines(self.test_cache, self.test_bldroot, False, False,
                                          self.test_src_mods_dir, self.fort_indent, None, {}, [], [])

        #Check that the output path matches what is expected:
        self.assertEqual(gen_path, expected_path)

#################################################
#Run unit tests if this script is called directly
#################################################

if __name__ == "__main__":
    unittest.main()

############
#End of file
############
