#!/usr/bin/env python3

"""
Adapter: translate xdsl_ccpp's --emit-resolved-vars JSON artifact
(capgen_v1_parity_backlog.md Stage 3) into ResolvedVar records.

Lives here, in CAM-SIMA's own repo, rather than in xdsl_ccpp -- CAM-SIMA
already depends on real ccpp-framework via its own submodule, so it's the
one piece of this whole picture that's supposed to know about a specific
framework's native shape. xdsl_ccpp's own repo never needs to know
ResolvedVar exists.
"""

import json

from resolved_var import ResolvedVar

# xdsl_ccpp's own dimension-standard-name classification -- reused rather
# than re-implemented here, since CAM-SIMA's build already depends on
# xdsl_ccpp being installed to generate code with it in the first place.
from xdsl_ccpp.util.ccpp_conventions import is_horizontal_dimension, is_vertical_dimension


def _vertical_dim_name(dim_names):
    """Return 'lev'/'ilev' for the recognized vertical dimension in
    dim_names, matching capgen-v1's own local-name convention for these
    two standard dimensions (see write_init_files.py's get_dimension_info),
    or None if there isn't one.
    """
    for d in dim_names:
        if is_vertical_dimension(d):
            return "ilev" if "interface" in d.lower() else "lev"
    return None


def _to_resolved_var(record: dict) -> ResolvedVar:
    dim_names = record.get("dim_names") or []
    return ResolvedVar(
        standard_name=record["standard_name"],
        intent=record.get("intent") or "",
        is_protected=bool(record.get("is_protected")),
        is_advected=bool(record.get("is_advected")),
        is_constituent=bool(record.get("is_constituent")),
        # capgen_v1_parity_backlog.md Stage 7: xdsl_ccpp's
        # HostVariableMatchPass now records whether a matched host var came
        # from a HOST-type (vs MODULE-type) table (model_var_is_host_table),
        # surfaced here as is_host_table_var -- was hardcoded False through
        # Stage 4/6, since that distinction wasn't tracked at all before.
        is_host_table_var=bool(record.get("is_host_table_var")),
        is_optional=bool(record.get("is_optional")),
        host_module=record.get("model_module_name"),
        local_name=record.get("model_var_name"),
        # capgen_v1_parity_backlog.md Post-Stage-7 (DDT-chain gap):
        # suite_cap.py's _resolved_var_record already sets these two to
        # model_var_name for every record (matching the pre-fix behavior
        # here exactly for a non-DDT arg); _apply_ddt_chain then overwrites
        # them in place for a DDT member match -- import_name becomes the
        # real instance variable (e.g. "phys_state"), call_expr the full
        # "%"-chain (e.g. "phys_state%theta"). Reading them straight off
        # the record (rather than re-deriving from model_var_name here)
        # is what makes DDT resolution flow through to this adapter at all.
        import_name=record.get("import_name") or record.get("model_var_name"),
        call_expr=record.get("call_expr") or record.get("model_var_name"),
        dimensions=list(dim_names),
        has_horizontal_dim=any(is_horizontal_dimension(d) for d in dim_names),
        vertical_dim_name=_vertical_dim_name(dim_names),
        # array_ref_dims: _apply_ddt_chain populates this (as a list of
        # standard names) for a DDT member with an array-section subscript;
        # every other record's own base default is an empty list ([] ->
        # None here, matching ResolvedVar's own "can't derive this, leave
        # None" convention). intrinsic_element_names has no xdsl_ccpp-side
        # producer at all yet (DDT *array expansion*, not member/subscript
        # resolution -- a different capability; see capgen_v1_parity_
        # backlog.md Stage 4) -- every fixture validated through Stage 7
        # needed only member/subscript resolution, not array expansion, so
        # this stays None until a fixture actually exercises that path.
        array_ref_dims=record.get("array_ref_dims") or None,
        intrinsic_element_names=None,
    )


def _host_var_to_resolved_var(standard_name: str, entry: list) -> ResolvedVar:
    """Build a minimal ResolvedVar from one entry of the JSON's top-level
    "host_vars" dict (see XdslCcppResolvedVars.__init__) -- a real host
    variable that's never itself a scheme argument (e.g. a DDT member's
    array-section index variable), so it never appears in any phase's own
    call list and needs a separate, sparser construction path than
    _to_resolved_var's per-call-list records.

    entry is [local_name, module_name] (cap_shared.py's _build_host_var_map
    result, serialized by suite_cap.py's _write_resolved_vars). This is
    genuinely less information than a full call-list record -- no intent,
    dimensions, or is_host_table_var/is_protected data survives the JSON
    round-trip for these entries -- so is_host_table_var/is_protected
    default to False here rather than being guessed. Every fixture this
    fallback has been validated against (capgen_v1_parity_backlog.md
    Post-Stage-7) is a MODULE-type index/dimension constant, for which
    those defaults are correct; revisit if a HOST-type or protected
    variable is ever reached only through this fallback.
    """
    local_name, module_name = entry[0], entry[1]
    return ResolvedVar(
        standard_name=standard_name,
        intent="in",
        host_module=module_name,
        local_name=local_name,
        import_name=local_name,
        call_expr=local_name,
    )


class XdslCcppResolvedVars:
    """Loads a Stage-3 --emit-resolved-vars JSON file and exposes it as
    ResolvedVar records, matching the shape write_init_files.py's
    refactored consumption code (Stage 6) expects from either backend.
    """

    def __init__(self, json_path: str):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        # Exclude suite-owned (cap-allocated scratch) variables from the
        # call list -- write_init_files.py only needs host-matched variables
        # (those the host model provides at initialization). Suite-owned vars
        # are allocated by the cap itself and never read from initial conditions.
        self._by_phase: dict = {
            phase: [_to_resolved_var(r) for r in records
                    if r.get("ownership_kind") != "suite_owned"]
            for phase, records in data["phases"].items()
        }
        # Flat lookup across every phase's records, deduped by standard_name
        # (first occurrence wins) -- backs resolve_by_standard_name for the
        # recursive expansion write_init_files.py's real code already does
        # (_find_and_add_host_variable, _get_host_model_import). Only finds
        # names that happen to appear in at least one phase's own resolved
        # list; self._host_vars below (capgen_v1_parity_backlog.md
        # Post-Stage-7) is the fallback for a real host variable that's
        # never itself a scheme argument (e.g. a DDT member's own
        # array-section index variable), so never appears in any phase's
        # call list at all.
        self._flat: dict = {}
        for records in self._by_phase.values():
            for rv in records:
                self._flat.setdefault(rv.standard_name, rv)
        # Top-level "host_vars" key (suite_cap.py's _write_resolved_vars):
        # standard_name -> [local_name, module_name] over every HOST/MODULE
        # variable cap_shared.py's _build_host_var_map saw, not just ones
        # some suite call happened to resolve. Absent entirely when the
        # generating xdsl_ccpp build predates this key -- treated as empty,
        # not an error, so this adapter degrades to the old, narrower
        # per-phase-only lookup rather than raising KeyError.
        self._host_vars: dict = data.get("host_vars") or {}

    def call_list(self, phase: str) -> list:
        """Return the ResolvedVar list for one CCPP lifecycle phase."""
        return self._by_phase.get(phase, [])

    def resolve_by_standard_name(self, standard_name: str) -> "ResolvedVar | None":
        """Look up one variable by standard name, first in the per-phase
        flat lookup, then (capgen_v1_parity_backlog.md Post-Stage-7) in the
        full host-variable dictionary for names that never appear in any
        phase's own call list -- backs the same recursive expansion
        write_init_files.py's real code does for DDT sub-elements and
        array-reference index variables (_find_and_add_host_variable,
        _get_host_model_import).
        """
        found = self._flat.get(standard_name)
        if found is not None:
            return found
        entry = self._host_vars.get(standard_name)
        if entry is None:
            return None
        return _host_var_to_resolved_var(standard_name, entry)
