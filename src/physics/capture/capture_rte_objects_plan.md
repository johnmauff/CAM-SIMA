# Capturing the RTE-RRTMGP objects: `ty_gas_concs` and the handler design

BACKLOG ID: `scheme-io-capture-rte-objects` (stage 3), in xdsl-ccpp's
`BACKLOG.md`. This document lives beside the handlers it describes, in
CAM-SIMA `src/physics/capture/`. It records the design discussion of
2026-11-13: where the capture handlers live, which registry fields can be
generated, and how a `ty_gas_concs` handler can learn the object's shape.

**Decision (2026-11-13):**
- **Long term:** an upstream rte-rrtmgp PR adding `ty_gas_concs` shape
  getters. See "Ways to get the shape" (option 1) and "Further motivations"
  for the PR's content and arguments.
- **For now:** the ESCOMP wrapper (option 2), so stage 3 can go ahead. When
  the upstream getter is released and the pin is bumped, the wrapper's
  `get_ncol`/`get_nlay` forward to RTE and its copy of the shape goes away.
- **Status:** the wrapper and the `ty_gas_concs_ccpp` handler are
  implemented (xdsl-ccpp CHANGELOG, stage 3a).

## Where things stand

- **Stage 1 (xdsl-ccpp, committed).** Capture handlers come from a registry
  file passed with `--capture-ddt-handlers`
  (`xdsl_ccpp/util/capture_ddt_handlers.py`).
- **Stage 2 (CAM-SIMA, to commit).** Handlers for the optical properties, the
  LW source functions and the fluxes. Capture c08f passed, and the six new
  replays (`rrtmgp_pre_run`, sw/lw `aerosols`, `sw_rte`, sw/lw
  `calculate_fluxes`) pass on CPU. The GPU replays are pending.
- **Still skipped.** `rrtmgp_pre_init` and `rrtmgp_post_run` need
  `ty_gas_concs`. `rrtmgp_lw_rte_run`, `inputs`, both `mcica` and both
  `gas_optics` also need `kdist`, and some of these are blocked by
  `capture-interpolate-data` as well.

## Where the handlers live

The handlers are in CAM-SIMA `src/physics/capture/`, beside this document:

- `ccpp_capture_rte_objects.F90`, the handler module. Its `device_enter` and
  `device_exit` routines (stage 3c) keep an object on the device across a
  GPU test driver's call of a scheme whose OpenACC names it. The drivers
  model production with all schemes on the GPU and the data resident, not
  today's per-scheme data regions; the schemes and caps are unchanged;
- `ccpp_netcdf_reader.F90`, a plain-NetCDF `ccpp_io_reader` (stage 3b), so
  a test driver can run the gas optics init that loads the coefficient
  file; a `driver_source`, so it never reaches the model, which has PIO's;
- `capture_handlers.txt`, the registry.

`cam_autogen.py` passes the registry when a capture is configured. The
directory isn't in `buildlib`'s Filepath, so normal builds never compile it.

The files were first written into atmospheric_physics
(`schemes/rrtmgp/objects/`) and moved before being committed. Both are
xdsl-ccpp test tooling: the registry has an xdsl-ccpp-only format, and the
handler module uses `ccpp_capture_mod`, which is xdsl-ccpp's capture runtime.
Keeping them in atmospheric_physics would tie a portable scheme repo to one
cap generator, against its AGENTS.md. They don't belong in xdsl-ccpp either,
because xdsl-ccpp holds no physics knowledge.

## Can the registry be generated?

For each handler line:

| Field | Derivable? |
|---|---|
| `type_module` | Yes. The DDT's `.meta` file names the module that declares the type. |
| `module`, `write`, `read`, `compare` | Yes, by a naming convention: scan a handler directory for public routines named `<type>_capture_{write,read,compare}`. |
| `source` | Yes. It's the files in that directory. |
| `dims=` | No (next section). |

A convention would replace the `.txt` file: `cam_autogen` passes a directory,
and xdsl-ccpp discovers the handlers in it. The costs:

- A misspelled routine silently means "not handled" instead of a `file:line`
  error.
- `dims` would still need a way to be declared. The natural one is a CCPP
  `.meta` file for the handler module, with standard names on the dummy
  arguments, but that is still written by hand.

The Fortran handlers themselves can't be generated. Rebuilding an RTE object
means knowing its public API and calling it in order: `init`, then
`alloc_2str`, then the arrays, then `set_top_at_1`.

**Decision.** Keep the hand-written registry. It's five lines and changes only
when someone writes a new handler. Revisit the convention if handlers for
other packages appear.

## Why `dims=` can't be derived

Only `ty_gas_concs` needs `dims=`. Every other RTE object reports its own size
through public calls. `ty_gas_concs` keeps `ncol` and `nlay` private with no
getter, and `get_vmr(gas, array)` needs an array of exactly the stored shape.
So the write handler must be told the extents
(`write(name, obj, ncol, nlay)`). `dims=` tells the generated cap which of the
scheme call's arguments, named by standard name, to pass.

Nothing in the type, its metadata or the handler's interface gives that
mapping. The size was fixed by whichever scheme last called `set_vmr`, and only
that scheme's source shows it:

| Scheme | Array given to `set_vmr` | Column extent |
|---|---|---|
| `rrtmgp_lw_gas_optics_pre` | `gas_vmr(ncol, nlay)` | `horizontal_loop_extent` |
| `rrtmgp_sw_gas_optics_pre` | `gas_vmr(nday, nlay)` | `daytime_columns_dimension` |

Both objects have the same type, but the SW one holds only the daylit columns.
The layer extent is `number_of_vertical_layers_in_RRTMGP`, not the model's
level count.

**This exposes a flaw in the stage-1 design.** `dims=` is keyed per type, one
list per type, so it can't express the SW/LW difference. The original stage 3
plan (`dims=horizontal_loop_extent,vertical_layer_dimension`) was wrong in two
ways: the column extent differs between SW and LW, and the layer standard name
is wrong. If `dims=` is kept, it would have to be bound per object, for
example keyed on the argument's standard name, since the SW and LW
concentrations have different standard names in the host.

## How RTE-RRTMGP handles the shape

RTE-RRTMGP has no setter and no getter for `ncol` and `nlay`. Line numbers
below are from v1.9.2 `gas-optics/mo_gas_concentrations.F90`.

| Call | Effect on `ncol` / `nlay` |
|---|---|
| `init(gas_names)` | Leaves both alone; they stay 0. |
| `set_vmr(gas, scalar)` | No change. |
| `set_vmr(gas, w(nlay))` | The first call sets `nlay` (:201); later calls must match (:199). |
| `set_vmr(gas, w(ncol,nlay))` | The first call sets both (:265, :271); later calls must match (:262, :268). |
| `get_subset(start, n, subset)` | Subset gets `nlay`, and `ncol = n`, or 0 if the parent's `ncol` is 0 (:474-475). |
| `reset()` | Sets both to 0 (:523-524). |

`get_vmr` only checks the caller's shape (:394-397), and its error message
doesn't include the expected size. When `ncol` is 0, no gas has a column
dimension: they were all set as scalars or profiles, and `get_vmr` broadcasts.

For the handler, this means:

- **Write.** A getter is the only missing piece.
- **Read.** No setter is needed: `set_vmr` with arrays of the captured shape
  recreates `ncol` and `nlay` exactly.

## RTE-RRTMGP versions (checked 2026-11-13)

- **The vendored copy is unpatched.** `schemes/rrtmgp/ext` is the submodule
  earth-system-radiation/rte-rrtmgp at `77ff83c`, which is exactly tag `v1.9.2`
  (2025-07-08). It matches the atmospheric_physics pin and `.gitmodules`
  (`fxtag = v1.9.2`), and has no local changes.
- **No release has a getter.** v1.9.2, v1.9.3 (latest release, 2026-06-14) and
  upstream `main` (`bfcb7a7`, 2026-11-12) all keep `ncol` and `nlay` private.
  The public procedures are `init`, `reset`, `set_vmr`, `get_vmr`, `get_subset`,
  `get_num_gases` and `get_gas_names`.
- **No related issue or PR was found** among the 100 most recent; code search
  needs authentication. The related closed items are #406 (finalization in
  `mo_gas_concentrations`), #390 (non-conformant OpenACC in it) and #433 (GPU
  fixes).
- **v1.9.3 moved the file** to `rte/frontend/gas-optics-template/`, so a pin
  bump also means updating atmospheric_physics' build paths. #405 and #433
  (OpenACC correctness) may be worth the bump for `gpu-fphystest-rrtmgp`
  anyway. Not checked against our cases.

## Ways to get the shape

1. **Upstream rte-rrtmgp getters.** Add `get_ncol` and `get_nlay` as pure
   getters, like `get_num_gases`, returning raw values (0 kept). This is the
   right home and always correct. It waits on their release and an
   atmospheric_physics pin bump, which comes with the v1.9.3 path move.
2. **ESCOMP wrapper tracking** (next section). This needs no RTE change.
3. **`dims=` bound per object by standard name.** This needs no physics
   change, but the extents are written by hand, and stage 1's per-type `dims=`
   has to be reworked.
4. **Patch the vendored RTE copy.** Not recommended: the submodule drifts from
   its tag. Use it only as a stopgap while option 1 is pending.

With option 1 or 2, `dims=` has no user. Stage 1's `dims` key, the
`std_name_to_param` mapping, the extra driver arguments and the "missing
handler dim" skip reason could then be removed.

## The ESCOMP wrapper modification (option 2)

`schemes/rrtmgp/objects/ccpp_gas_concentrations.F90` today has only
`type :: ty_gas_concs_ccpp; type(ty_gas_concs) :: gas_concs; end type`. The
wrapper would own every call that changes the shape:

```fortran
type, public :: ty_gas_concs_ccpp
   type(ty_gas_concs) :: gas_concs
   integer, private   :: ncol = 0, nlay = 0   ! shape RTE has recorded
contains
   procedure, public  :: init                 ! forwards
   procedure, private :: set_vmr_scalar, set_vmr_1d, set_vmr_2d
   generic,   public  :: set_vmr => set_vmr_scalar, set_vmr_1d, set_vmr_2d
   procedure, public  :: reset                ! forwards, then ncol = nlay = 0
   procedure, public  :: get_ncol, get_nlay
end type
```

Each `set_vmr` forwards to RTE first, then copies the shape only if RTE
accepted the call: the 2-D version sets both, the 1-D version sets `nlay`, and
the scalar version sets neither. Copying on every success matches RTE, because
RTE rejects any shape that differs from the first.

**Scheme edits:** six lines, each dropping the inner `%gas_concs`:

- `rrtmgp_inputs.F90:276,301` and `rrtmgp_pre.F90:39` (`init`);
- `rrtmgp_sw/lw_gas_optics_pre.F90:117,118` (`set_vmr`);
- `rrtmgp_post.F90:79,96` (`reset`).

The read-only uses stay as they are: the `gas_optics` calls in
`rrtmgp_sw/lw_gas_optics.F90`, the `load` of `available_gases`, and the
`!$acc data copyin(... gas_concs%gas_concs)` clauses. The new integers sit
outside the inner object, so the OpenACC data movement doesn't change.
Answers are bit-for-bit.

**The handler** (CAM-SIMA `src/physics/capture/`):

- **Write:** `gas_names`, `ncol`, `nlay`, and each set gas's values via
  `get_vmr` into `(max(ncol,1), max(nlay,1))`.
- **Read:** `init`, then the wrapper's `set_vmr` with the recorded shape. This
  rebuilds RTE's shape and the wrapper's copy.
- **Compare:** names, shape and values.
- **Self-check:** if code bypassed the wrapper, the stale shape makes `get_vmr`
  fail with RTE's wrong-size error. The handler reports that as a capture
  failure, so a stale copy is never recorded silently.

One subtlety: a scalar-only gas, which RTE stores as 1×1, is rebuilt at full
size. `get_vmr` returns the same values either way, and CAM-SIMA sets every gas
in 2-D anyway.

**Pros:**
- ESCOMP-only; no RTE release or pin bump needed.
- The tracking is in one place.
- `get_ncol`/`get_nlay` stay the same interface if RTE later adds getters: the
  wrapper forwards and drops its copy, and the schemes and handler don't
  change.
- Removes `dims=`.

**Cons:**
- It duplicates RTE state, and correctness relies on convention (the
  handler's self-check catches a break).
- Six scheme lines change mostly for testing.
- It needs an ESCOMP atmospheric_physics PR (bit-for-bit, `Assisted-by`
  trailer, answer impact "none").

## Reasons for the change besides testing

Testing is the main reason. The other benefits are modest:

- **Performance: none.** Two integer assignments per `set_vmr`, which is called
  once per gas per radiation call, cost nothing measurable and save nothing.
  The getter doesn't change the gas-optics work or any data movement.
- **Simplicity: small, and mostly potential.** No scheme reads gas
  concentrations back today (no `get_vmr`, `get_num_gases` or `get_gas_names`
  outside `ext/`). A shape getter would help future code that does:
  diagnostics writing a gas's vmr, or a consistency check. Such code wouldn't
  have to work out separately whether an object is sized by `nday` or `ncol`.
- **Clearer errors.** A scheme could check the object's shape against its own
  extents and report which extent is wrong and by how much. RTE's message only
  says "array is wrong size (ncol)".
- **Isolation from RTE API changes.** With the wrapper owning `init`,
  `set_vmr` and `reset`, an RTE interface change touches one module, not
  four schemes. v1.9.3 changed only file locations, not this API, so the
  benefit is real but has no current example.
- **Debugging.** Being able to dump an object's shape and contents helps when
  RRTMGP gives unexpected answers. This is the capture handler's purpose
  generalized.

**Does the wrapper remove complexity from ESCOMP?** No (checked
2026-11-13). The user noted that a change which cleans up complexity at no
performance cost would be an easier sell. The wrapper doesn't qualify:

- It adds about 60 lines to `ccpp_gas_concentrations.F90` and removes none.
- The six scheme edits are renames, not simplifications.
- The schemes have no code working around the missing shape. The gas-optics
  runs need `ncol` and `rrtmgp_phys_blksz` for their other arrays anyway.
  `gas_optics_pre` sizes `gas_vmr` from its own `nday`/`ncol`. `rrtmgp_post`
  just calls `reset`.

The simplification is real, but it lands in xdsl-ccpp and in the capture
handler (stage 1's `dims=` machinery removed), not in ESCOMP. ESCOMP
reviewers wouldn't see it.

For option 1 (upstream getters), the case is stronger and doesn't depend on
CAM: `ty_gas_concs` already exposes `get_num_gases` and `get_gas_names`, and
a shape getter completes that introspection API. A caller holding an object
from elsewhere currently can't size a `get_vmr` buffer without outside
knowledge.

Further motivations for the upstream getter, beyond symmetry (checked
2026-11-13):

- **RTE's own tests need it.** `tests/check_equivalence.F90`
  (`lw_clear_sky_vr` and its SW twin, :490-520) copies a `ty_gas_concs` with
  vertically reversed layers. The comment there reads: "No direct access to
  gas concentrations so use the classes". The test sizes its buffer as
  `vmr(ncol,nlay)` from the test's own variables. Any generic routine that
  transforms an object it receives this way (reversing orientation, a deep
  copy, serialization, a capture) can't size the buffer without the shape.
- **Deep copy goes through `get_subset(1, ncol, copy)`**
  (`tests/check_variants.F90:158`, `check_equivalence.F90:155`). That also
  needs `ncol` from outside: copying an object you were handed takes a getter.
- **Upstream already plans this encapsulation.** `mo_gas_optics_rrtmgp.F90`
  has three comments (:1222, :1412, :1898): "Should replace gas_names with
  get_gas_names() and make gas_names private in ty_gas_concs". Shape getters
  continue that direction.
- **Possible bug to bundle (my reading, untested).** In `get_subset_range`,
  `if(this%ncol > 0 .and. start > this%ncol .or. start+n-1 > this%ncol)`
  parses as `(ncol > 0 .and. start > ncol) .or. (start+n-1 > ncol)`. With
  `ncol = 0`, meaning no gas has a column dimension, every `n >= 1` is
  rejected. That contradicts the subset code just below
  (`merge(n, 0, this%ncol > 0)` and the "ncol = 0 means no gas exploits this
  dimension" comment). The intended guard is presumably
  `this%ncol > 0 .and. (start > this%ncol .or. start+n-1 > this%ncol)`. The
  error messages in `get_subset` also say `gas_concs%get_vmr`, a copy-paste
  slip. Both are still present on upstream `main` (`bfcb7a7`, :521-525).

## Open decisions (stage 3)

1. **Shape source: decided.** The ESCOMP wrapper (option 2) now, the
   upstream getter (option 1) later. The wrapper is an interim measure: it
   removes no complexity from ESCOMP, so it may never go upstream as it
   stands.
2. **Order:** start stage 3 with the `kdist` setup replay (needs no
   `gas_concs`), then the `gas_concs` handler.
3. **`dims=`:** remove it once a getter exists, or rework it to bind per
   object by standard name. Nothing uses it today.
4. **Pin bump** to v1.9.3 or later (path move; OpenACC fixes #405 and #433),
   for `gpu-fphystest-rrtmgp`.
