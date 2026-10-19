"""Composite-scheme version of atmospheric_physics' suite_rrtmgp.xml.

What this file is
-----------------
The suite itself: what a CAM-SIMA physics configuration author writes.  It
calls CAM's radiation adapter (cam_rrtmgp_adapter.py), which calls the
exchangeable RRTMGP package (rrtmgp_package.py).  It defines exactly the
same suite as atmospheric_physics' flat test/test_suites/suite_rrtmgp.xml.

Because this file is named suite_rrtmgp.py and sits in the case's
SourceMods/src.cam, ``--physics-suites rrtmgp`` selects it ahead of the XML
suite (cam_autogen.py; requires CCPP_GENERATOR=xdsl_ccpp).  cam_autogen.py
runs it to find the schemes, then passes it to xdsl_ccpp with ``--py``.
Copied from xdsl-ccpp's examples/rrtmgp_composite.

How this reduces the complexity CCPP exposes
--------------------------------------------
suite_rrtmgp.xml lists 40 scheme entries and 2 loops; its author must know
every RRTMGP and CAM radiation scheme and their exact order.  Here the suite
author writes two calls and needs to know only that ``cam_rrtmgp()`` means
"CAM's radiation".  The detail still exists, but it is layered: RRTMGP's
internal order lives in the package, CAM's radiation policy in the adapter,
and the physics configuration here.  Each layer is read and changed on its
own, and none of the three contains a file path.
"""

from xdsl_ccpp.frontend.py_api import ccpp_scheme_ref, ccpp_suite, export_suite

from cam_rrtmgp_adapter import cam_rrtmgp

# Test-only scheme from atmospheric_physics' test suite: sets the constituent
# values a standalone radiation test needs.  Part of the suite, not of the
# radiation package or the adapter.
initialize_constituents = ccpp_scheme_ref("initialize_constituents")


# In a CCPP suite class, each method is a group recorded by @ccpp_suite,
# not a real method: it takes no 'self', and the class holds only groups.
# pylint: disable=no-method-argument,too-few-public-methods
@ccpp_suite("rrtmgp", version="1.0")
class RrtmgpSuite:
    """The 'rrtmgp' suite (its name comes from @ccpp_suite, not the class)."""

    def physics_after_coupler():
        """Group run after the coupler: CAM-SIMA's RRTMGP radiation."""
        initialize_constituents()
        cam_rrtmgp()


if __name__ == "__main__":
    export_suite(RrtmgpSuite)
