#!/usr/bin/env python3

"""
Adapter: translate real capgen-v1's CCPPDatabaseObj/Var objects into
ResolvedVar records.

Lives here, in CAM-SIMA's own repo, rather than in ccpp-framework -- this
is the one piece of the whole ResolvedVar picture that's supposed to know
about a specific CCPP-framework implementation's native shape. Any other
backend would get its own equally small adapter module alongside this one.
"""

# capgen-v1's own dimension-standard-name classification -- reused rather
# than re-implemented here. Already imported the same way by
# write_init_files.py's real code, so this module is already on the path
# wherever that one runs.
from var_props import is_horizontal_dimension, is_vertical_dimension
from parse_source import CCPPError

from resolved_var import ResolvedVar


def _vertical_dim_name(dimensions):
    """Return 'lev'/'ilev' for the recognized vertical dimension among
    <dimensions>, matching resolved_var_xdsl_ccpp.py's identical convention
    (so both backends' adapters report this the same way), or None if there
    isn't one.
    """
    for d in dimensions:
        if is_vertical_dimension(d):
            return "ilev" if "interface" in d.lower() else "lev"
    return None


def _array_ref_dims(var):
    """Return the standard names of <var>'s array-reference index
    variables (e.g. the "bar" in local_name "foo(bar,:)"), or None if
    <var>'s local_name isn't an array reference at all.

    Mirrors write_init_files.py's own _get_host_model_import exactly:
    a ':' entry is a plain array-section colon, not an index variable
    needing its own resolution, so it's dropped.
    """
    aref = var.array_ref()
    if not aref:
        return None
    dims = [d.strip() for d in aref.group(2).split(",") if d.strip() != ":"]
    return dims or None


def _intrinsic_element_names(var):
    """Return the standard names of <var>'s named intrinsic sub-elements
    (DDT case), or None.

    intrinsic_elements() also returns a var's *own* standard_name as a bare
    string when it's already a leaf/intrinsic variable with nothing to
    expand -- write_init_files.py's real _find_and_add_host_variable only
    ever acts on the list case (`isinstance(ielem, list)`), so mirror that
    exactly here rather than passing the bare-string case through as if it
    were a real sub-element list.
    """
    try:
        ielems = var.intrinsic_elements()
    except CCPPError:
        # CCPP framework DDTs (e.g. ccpp_constituent_prop_ptr_t) are not in
        # capgen's DDT library. Treat them as leaf variables — no expansion.
        return None
    return ielems if isinstance(ielems, list) else None


def _to_resolved_var(var, host_dict) -> ResolvedVar:
    dimensions = list(var.get_dimensions())
    return ResolvedVar(
        standard_name=var.get_prop_value("standard_name"),
        intent=var.get_prop_value("intent") or "",
        is_protected=bool(var.get_prop_value("protected")),
        is_advected=bool(var.get_prop_value("advected")),
        is_constituent=bool(var.get_prop_value("constituent")),
        is_host_table_var=bool(var.host_interface_var),
        is_optional=bool(var.get_prop_value("optional")),
        # Populated regardless of is_host_table_var -- matching
        # write_init_files.py's real _get_host_model_import, which reads
        # source.name unconditionally and relies on the separate
        # is_host_table_var/is_constituent flags (not host_module itself)
        # to decide whether a `use` statement is actually needed.
        host_module=var.source.name,
        # Bare leaf name -- for a DDT sub-element (VarDDT),
        # get_prop_value('local_name') delegates to the *leaf* field
        # (confirmed directly: returns "theta", not "phys_state" or
        # "phys_state%theta"). Matches write_init_files.py's IC-name
        # fallback, which needs exactly this (the netCDF field-name
        # convention), not a use-import name or a full call expression.
        local_name=var.get_prop_value("local_name"),
        # Root-level bare name, for `use module, only: <name>` statements.
        # `.var` is VarDDT's own property returning a base-class view of
        # self (bypassing the leaf-delegating override) -- for a DDT
        # sub-element this gives "phys_state", the actual use-associated
        # name; for a plain (non-DDT) var, `.var` is just self, so this is
        # identical to local_name.
        import_name=var.var.get_prop_value("local_name"),
        # Full call-site expression -- resolves DDT chains ("phys_state%
        # theta") and array-ref indices ("foo(bar)") via host_dict, exactly
        # matching what real capgen-v1's own generated Fortran emits at a
        # call site. Reduces to local_name for every plain scalar/array var.
        call_expr=var.call_string(host_dict),
        dimensions=dimensions,
        has_horizontal_dim=any(is_horizontal_dimension(d) for d in dimensions),
        vertical_dim_name=_vertical_dim_name(dimensions),
        array_ref_dims=_array_ref_dims(var),
        # Matches write_init_files.py's own _find_and_add_host_variable
        # call convention exactly (no ddt_lib) -- correct for every fixture
        # that function already handles today.
        intrinsic_element_names=_intrinsic_element_names(var),
    )


class Capgenv1ResolvedVars:
    """Wraps a real capgen-v1 CCPPDatabaseObj and exposes it as ResolvedVar
    records, matching the shape write_init_files.py's consumption code
    expects from any backend.
    """

    def __init__(self, cap_database):
        self._cap_database = cap_database
        self._host_dict = cap_database.host_model_dict()
        # Cache ResolvedVar construction keyed by the underlying real Var
        # object's identity (Var has no __eq__/__hash__ override, so this
        # is plain identity hashing) -- real capgen-v1 returns the *same*
        # Var instance from repeated find_variable()/call_list() lookups of
        # the same variable (e.g. an inout var appearing in both a phase's
        # input and output roles), and write_init_files() itself dedupes
        # its required-variable lists via identity (OrderedDict.fromkeys).
        # Without this cache, resolving the same variable twice would
        # produce two distinct ResolvedVar objects that dedup can no longer
        # tell apart, silently duplicating the variable in generated output.
        self._cache = {}

    def _resolved(self, var) -> "ResolvedVar | None":
        if var is None:
            return None
        cached = self._cache.get(var)
        if cached is None:
            cached = _to_resolved_var(var, self._host_dict)
            self._cache[var] = cached
        # end if
        return cached

    def call_list(self, phase: str) -> list:
        """Return the ResolvedVar list for one CCPP lifecycle phase."""
        return [
            self._resolved(v)
            for v in self._cap_database.call_list(phase).variable_list()
        ]

    def resolve_by_standard_name(self, standard_name: str) -> "ResolvedVar | None":
        """Look up one variable by standard name in the full host-model
        dictionary (not just a single phase's call list) -- backs the
        recursive expansion write_init_files.py's real code already does
        (_find_and_add_host_variable, _get_host_model_import) for DDT
        sub-elements and array-reference index variables.
        """
        return self._resolved(self._host_dict.find_variable(standard_name))
