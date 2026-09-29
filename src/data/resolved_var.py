#!/usr/bin/env python3

"""
ResolvedVar: a backend-neutral description of one variable required by a
CCPP suite at one lifecycle phase.

Defined once, here, so write_init_files.py's actual Fortran-generation
logic never has to know whether the data came from real capgen's
CCPPDatabaseObj/Var objects or from xdsl_ccpp's native
--emit-resolved-vars JSON artifact -- each backend gets its own small
adapter module (resolved_var_capgen.py, resolved_var_xdsl_ccpp.py)
translating its own native shape into this one.

Every field here corresponds to a property write_init_files.py's own
Fortran-generation logic actually reads off a host-model variable --
audited directly against that code (gather_ccpp_req_vars,
_find_and_add_host_variable, collect_host_var_imports, get_dimension_info,
write_ic_params/write_ic_arrays), not guessed.
"""

from dataclasses import dataclass, field

# The six CCPP suite lifecycle phases, in the order capgen's own
# CCPP_STATE_MACH.transitions() returns them -- kept here as a plain
# constant so write_init_files.py doesn't need a real-capgen import
# just to iterate over phase names.
CCPP_PHASES = (
    "register", "initialize", "finalize",
    "timestep_initial", "timestep_final", "run",
)

# Phases that run before the host ever calls physics_read_data -- shared by
# any backend's first_intent_by_suite() implementation (backs
# write_init_files.py's gather_set_before_use_vars): a variable a suite
# only sets during one of these phases hasn't actually been set yet by the
# time physics_read_data needs to decide whether to skip reading it.
PRE_READ_PHASES = {"register", "initialize"}

# Recognized horizontal/vertical dimension standard-name forms, ported from
# capgen's var_props.py so write_init_files.py doesn't need a capgen
# import. xdsl_ccpp keeps its own independent copy in ccpp_conventions.py.
_CCPP_HORIZONTAL_DIMENSIONS = [
    "ccpp_constant_one:horizontal_dimension",
    "ccpp_constant_one:horizontal_loop_extent",
    "horizontal_loop_begin:horizontal_loop_end",
    "horizontal_dimension", "horizontal_loop_extent",
]
_CCPP_VERTICAL_DIMENSIONS = [
    "ccpp_constant_one:vertical_layer_dimension",
    "ccpp_constant_one:vertical_interface_dimension",
    "vertical_layer_dimension", "vertical_interface_dimension",
    "vertical_layer_index", "vertical_interface_index",
]


def is_horizontal_dimension(dim_name):
    """Return True if <dim_name> is a recognized horizontal dimension or
    index, otherwise False."""
    return dim_name in _CCPP_HORIZONTAL_DIMENSIONS


def is_vertical_dimension(dim_name):
    """Return True if <dim_name> is a recognized vertical dimension or
    index, otherwise False."""
    return dim_name in _CCPP_VERTICAL_DIMENSIONS


@dataclass(eq=False)
class ResolvedVar:
    """One variable required by a suite at one CCPP lifecycle phase.

    eq=False: identity-based equality/hashing, matching real capgen's
    own Var class (which has no __eq__/__hash__ override either) --
    write_init_files.py's own write_init_files() dedupes required-variable
    lists via OrderedDict.fromkeys(), which needs hashable, identity-
    comparable entries. The dataclass default (eq=True) would make this
    unhashable instead (a mutable dataclass with a generated __eq__ gets
    __hash__ set to None).
    """

    standard_name: str
    intent: str  # 'in' | 'out' | 'inout'
    is_protected: bool = False
    is_advected: bool = False
    is_constituent: bool = False
    # True iff this variable's own metadata table type is 'host' (passed to
    # physics via the host's argument list, not import-associated -- always
    # considered initialized). Distinct from host_module: a variable can be
    # host_module=None and still not be a host-table var (e.g. a framework
    # var like ccpp_error_message, which is neither).
    is_host_table_var: bool = False
    # True iff this variable is a whole-DDT-typed host variable (e.g. a
    # scheme argument of DDT type such as ccpp_model_constituents_t) rather
    # than a plain scalar/array or a DDT *sub-element* (VarDDT). A whole-DDT
    # host variable cannot be read from initial-conditions files -- the host
    # model initializes it at run time -- so write_init_files.py's
    # _find_and_add_host_variable excludes it from generated read/check
    # code. Defaults to False for backends that don't yet report it.
    is_ddt: bool = False
    is_optional: bool = False
    # Fortran module to `use` this variable from, or None if there's no
    # host-variable binding at all (e.g. framework vars like ccpp_error_message).
    # Note: host_module may still be set for constituents/host-table vars; rely on
    # is_constituent/is_advected/is_host_table_var to decide whether a `use` is needed.
    host_module: "str | None" = None
    # This variable's own declared (bare) name -- what write_init_files.py
    # uses as the default IC-file variable-name fallback. For a plain
    # scalar/array var this is also what's used at the Fortran call site.
    # For a DDT sub-element (e.g. "theta", a field of "phys_state"), this is
    # the *leaf* field's own bare name, distinct from both import_name and
    # call_expr below -- confirmed against real capgen's VarDDT, which
    # keeps these three genuinely different (get_prop_value('local_name')
    # delegates to the leaf field; call_string() builds the full chain; the
    # root var's own name is reached only via the separate `.var` property).
    # None if there's no host binding.
    local_name: "str | None" = None
    # The name to `use <host_module>, only: <import_name>` -- for a DDT
    # sub-element this is the *root* DDT variable's own name (e.g.
    # "phys_state", not "theta"), since that's what's actually
    # use-associated; the sub-element itself is reached through it. Each
    # adapter should set this equal to local_name when the two don't
    # differ (every non-DDT variable).
    import_name: "str | None" = None
    # The full Fortran expression to reference this variable by at an
    # actual call site, once import_name (if any) has been use-associated
    # -- for a DDT sub-element this is the dotted chain (e.g.
    # "phys_state%theta"); for an array-reference local_name, this has its
    # index variables resolved to their own local names. Each adapter
    # should set this equal to local_name when the two don't differ (every
    # plain scalar/array variable).
    call_expr: "str | None" = None
    dimensions: list = field(default_factory=list)  # dimension standard names
    has_horizontal_dim: bool = False
    vertical_dim_name: "str | None" = None  # 'lev' | 'ilev' | None
    # Both None in the common case. Set when this variable isn't
    # self-contained -- e.g. an array reference whose index variables need
    # their own resolution, or a DDT whose named intrinsic sub-elements each
    # need their own resolution -- and the caller's resolve_by_standard_name
    # lookup should be used to fetch each named entry as its own ResolvedVar.
    # An adapter whose backend can't derive this (e.g. one whose
    # introspection doesn't capture host-side DDT sub-element/array-index
    # representation) should leave both None.
    array_ref_dims: "list | None" = None
    intrinsic_element_names: "list | None" = None
