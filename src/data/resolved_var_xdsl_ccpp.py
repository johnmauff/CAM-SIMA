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
        # Not distinguished from local_name -- Stage 3's JSON records only
        # scheme-side resolved args, with no DDT-chain/array-ref local-name
        # decomposition (see array_ref_dims/intrinsic_element_names below).
        # Correct for every non-DDT, non-array-ref fixture validated so far
        # (Stage 4); revisit together with those two fields if a DDT
        # sub-element or array-ref var is ever exercised through this
        # backend (capgen_v1_parity_backlog.md Stage 4/6).
        import_name=record.get("model_var_name"),
        call_expr=record.get("model_var_name"),
        dimensions=list(dim_names),
        has_horizontal_dim=any(is_horizontal_dimension(d) for d in dim_names),
        vertical_dim_name=_vertical_dim_name(dim_names),
        # DDT/array-ref sub-resolution: not populated. See
        # capgen_v1_parity_backlog.md Stage 4 -- the host-side DDT
        # sub-element/array-index representation this needs isn't in
        # Stage 3's JSON, which only records scheme-side resolved args.
        array_ref_dims=None,
        intrinsic_element_names=None,
    )


class XdslCcppResolvedVars:
    """Loads a Stage-3 --emit-resolved-vars JSON file and exposes it as
    ResolvedVar records, matching the shape write_init_files.py's
    refactored consumption code (Stage 6) expects from either backend.
    """

    def __init__(self, json_path: str):
        with open(json_path) as f:
            data = json.load(f)
        self._by_phase: dict = {
            phase: [_to_resolved_var(r) for r in records]
            for phase, records in data["phases"].items()
        }
        # Flat lookup across every phase's records, deduped by standard_name
        # (first occurrence wins) -- backs resolve_by_standard_name for the
        # recursive expansion write_init_files.py's real code already does
        # (_find_and_add_host_variable, _get_host_model_import). Stage 3's
        # JSON has no separate "every host variable" registry, only
        # per-phase call lists, so this is an approximation: it only finds
        # names that happen to appear in at least one phase's own resolved
        # list, not the full host variable dictionary. Adequate for every
        # fixture validated in Stage 4 (index/dimension variables like
        # horizontal_dimension consistently appear in the same phase's own
        # list); revisit if a fixture needs a name that doesn't.
        self._flat: dict = {}
        for records in self._by_phase.values():
            for rv in records:
                self._flat.setdefault(rv.standard_name, rv)

    def call_list(self, phase: str) -> list:
        """Return the ResolvedVar list for one CCPP lifecycle phase."""
        return self._by_phase.get(phase, [])

    def resolve_by_standard_name(self, standard_name: str) -> "ResolvedVar | None":
        return self._flat.get(standard_name)
