! Scheme I/O capture handlers for the RTE-RRTMGP objects the RRTMGP CCPP
! schemes pass (xdsl_ccpp --capture-ddt-handlers; registry:
! capture_handlers.txt next to this file). The wrapper types are in
! atmospheric_physics schemes/rrtmgp/objects; this module is xdsl_ccpp
! test tooling and so lives in CAM-SIMA.
!
! The capture cannot read these types itself (private components, type
! extension, pointer components), so each one is recorded through RTE's
! public procedures, as one sub-group of the capture file's in/ or out/
! group:
!
!   ty_optical_props_1scl_ccpp, ty_optical_props_2str_ccpp
!     initialized; when initialized: band_lims_wvn, band_lims_gpt, name;
!     when tau is allocated: tau, top_at_1 (and ssa, g when allocated).
!   ty_source_func_lw_ccpp
!     the spectral part as above, and each allocated source array.
!   ty_fluxes_broadband_ccpp, ty_fluxes_byband_ccpp
!     each associated flux array.
!   ty_gas_concs_ccpp
!     the gas names, the shape the wrapper tracks (get_ncol/get_nlay; RRTMGP
!     keeps its own private), and each set gas's concentration.
!
! For each type: <prefix>_write(name, obj) records obj (generated caps),
! <prefix>_read(group, name, obj) rebuilds it with init/alloc and the
! captured values, and <prefix>_compare(group, name, obj, tolerance,
! call_count, n_failed) compares it with the captured values, reporting
! each part through ccpp_capture_report (generated test drivers). A part
! present on one side only, or of another shape, is a failure. Rebuilt
! flux pointers point at new arrays, never freed (the drivers are short).
!
! Device residency (GPU test drivers only): <prefix>_device_enter(obj) puts
! the RTE object inside the wrapper and each of its allocated (associated)
! arrays on the device, the parts the RRTMGP schemes' own data clauses
! name; <prefix>_device_exit(obj, copy_out) copies the arrays back when
! copy_out (an out/inout argument), else deletes them, and always deletes
! the object (copying it back could overwrite scalars a scheme set on the
! host). A test driver calls them around the call of a scheme whose
! directives name the argument, so the scheme finds its data present, as
! in a production run where the data stays on the device between schemes.
! The gas concentrations' contents are private (RTE copies them itself):
! only the object is put on the device.
!
! Uses xdsl_ccpp's capture runtime (ccpp_capture_mod): compiled only into
! capture builds and their test drivers, never into a normal model build.
module ccpp_capture_rte_objects

   use ccpp_kinds,            only: kind_phys
   use ccpp_capture_mod,      only: ccpp_capture, ccpp_capture_read, ccpp_capture_extents
   use ccpp_capture_mod,      only: ccpp_capture_begin_ddt, ccpp_capture_end_ddt
   use ccpp_capture_mod,      only: ccpp_capture_compare, ccpp_capture_report
   use mo_optical_props,      only: ty_optical_props, ty_optical_props_arry, name_len
   use mo_optical_props,      only: ty_optical_props_1scl, ty_optical_props_2str
   use mo_source_functions,   only: ty_source_func_lw
   use mo_fluxes,             only: ty_fluxes_broadband
   use mo_fluxes_byband,      only: ty_fluxes_byband
   use ccpp_optical_props,    only: ty_optical_props_1scl_ccpp, ty_optical_props_2str_ccpp
   use ccpp_source_functions, only: ty_source_func_lw_ccpp
   use ccpp_fluxes,           only: ty_fluxes_broadband_ccpp
   use ccpp_fluxes_byband,    only: ty_fluxes_byband_ccpp
   use ccpp_gas_concentrations, only: ty_gas_concs_ccpp

   implicit none
   private

   public :: ccpp_capture_rte_props_1scl_write, ccpp_capture_rte_props_1scl_read
   public :: ccpp_capture_rte_props_1scl_compare
   public :: ccpp_capture_rte_props_2str_write, ccpp_capture_rte_props_2str_read
   public :: ccpp_capture_rte_props_2str_compare
   public :: ccpp_capture_rte_sources_lw_write, ccpp_capture_rte_sources_lw_read
   public :: ccpp_capture_rte_sources_lw_compare
   public :: ccpp_capture_rte_fluxes_bb_write, ccpp_capture_rte_fluxes_bb_read
   public :: ccpp_capture_rte_fluxes_bb_compare
   public :: ccpp_capture_rte_fluxes_byband_write, ccpp_capture_rte_fluxes_byband_read
   public :: ccpp_capture_rte_fluxes_byband_compare
   public :: ccpp_capture_rte_gas_concs_write, ccpp_capture_rte_gas_concs_read
   public :: ccpp_capture_rte_gas_concs_compare
   public :: ccpp_capture_rte_props_1scl_device_enter, ccpp_capture_rte_props_1scl_device_exit
   public :: ccpp_capture_rte_props_2str_device_enter, ccpp_capture_rte_props_2str_device_exit
   public :: ccpp_capture_rte_sources_lw_device_enter, ccpp_capture_rte_sources_lw_device_exit
   public :: ccpp_capture_rte_fluxes_bb_device_enter, ccpp_capture_rte_fluxes_bb_device_exit
   public :: ccpp_capture_rte_fluxes_byband_device_enter
   public :: ccpp_capture_rte_fluxes_byband_device_exit
   public :: ccpp_capture_rte_gas_concs_device_enter, ccpp_capture_rte_gas_concs_device_exit

   character(len=*), parameter :: dims_band = 'band_limit,number_of_bands'
   character(len=*), parameter :: dims_gpt3 = 'ncol,nlay,number_of_gpoints'
   character(len=*), parameter :: dims_lev3 = 'ncol,nlev,number_of_gpoints'
   character(len=*), parameter :: dims_sfc = 'ncol,number_of_gpoints'
   character(len=*), parameter :: dims_flux = 'ncol,nlev'
   character(len=*), parameter :: dims_bnd_flux = 'ncol,nlev,number_of_bands'
   character(len=*), parameter :: dims_gases = 'number_of_gases'
   character(len=*), parameter :: dims_vmr = 'ncol,nlay'
   integer,          parameter :: gas_name_len = 32   ! RRTMGP's gas name length

contains

   ! ---------------------------------------------------------------------
   ! ty_optical_props_1scl_ccpp
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_props_1scl_write(name, obj)
      character(len=*),                 intent(in) :: name
      type(ty_optical_props_1scl_ccpp), intent(in) :: obj

      call ccpp_capture_begin_ddt(name)
      call write_arry(obj%optical_props)
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_props_1scl_write

   subroutine ccpp_capture_rte_props_1scl_read(group, name, obj)
      character(len=*),                 intent(in)    :: group, name
      type(ty_optical_props_1scl_ccpp), intent(inout) :: obj

      call read_arry(trim(group) // '/' // trim(name), obj%optical_props)
   end subroutine ccpp_capture_rte_props_1scl_read

   subroutine ccpp_capture_rte_props_1scl_compare(group, name, obj, tolerance, &
                                                  call_count, n_failed)
      character(len=*),                 intent(in)    :: group, name
      type(ty_optical_props_1scl_ccpp), intent(in)    :: obj
      real(kind_phys),                  intent(in)    :: tolerance
      integer,                          intent(in)    :: call_count
      integer,                          intent(inout) :: n_failed

      call compare_arry(trim(group) // '/' // trim(name), name, obj%optical_props, &
                        tolerance, call_count, n_failed)
   end subroutine ccpp_capture_rte_props_1scl_compare

   ! ---------------------------------------------------------------------
   ! ty_optical_props_2str_ccpp
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_props_2str_write(name, obj)
      character(len=*),                 intent(in) :: name
      type(ty_optical_props_2str_ccpp), intent(in) :: obj

      call ccpp_capture_begin_ddt(name)
      call write_arry(obj%optical_props)
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_props_2str_write

   subroutine ccpp_capture_rte_props_2str_read(group, name, obj)
      character(len=*),                 intent(in)    :: group, name
      type(ty_optical_props_2str_ccpp), intent(inout) :: obj

      call read_arry(trim(group) // '/' // trim(name), obj%optical_props)
   end subroutine ccpp_capture_rte_props_2str_read

   subroutine ccpp_capture_rte_props_2str_compare(group, name, obj, tolerance, &
                                                  call_count, n_failed)
      character(len=*),                 intent(in)    :: group, name
      type(ty_optical_props_2str_ccpp), intent(in)    :: obj
      real(kind_phys),                  intent(in)    :: tolerance
      integer,                          intent(in)    :: call_count
      integer,                          intent(inout) :: n_failed

      call compare_arry(trim(group) // '/' // trim(name), name, obj%optical_props, &
                        tolerance, call_count, n_failed)
   end subroutine ccpp_capture_rte_props_2str_compare

   ! ---------------------------------------------------------------------
   ! ty_source_func_lw_ccpp
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_sources_lw_write(name, obj)
      character(len=*),             intent(in) :: name
      type(ty_source_func_lw_ccpp), intent(in) :: obj

      call ccpp_capture_begin_ddt(name)
      call write_spectral(obj%sources)
      if (allocated(obj%sources%lay_source)) &
         call ccpp_capture('lay_source', obj%sources%lay_source, dim_names=dims_gpt3)
      if (allocated(obj%sources%lev_source)) &
         call ccpp_capture('lev_source', obj%sources%lev_source, dim_names=dims_lev3)
      if (allocated(obj%sources%sfc_source)) &
         call ccpp_capture('sfc_source', obj%sources%sfc_source, dim_names=dims_sfc)
      if (allocated(obj%sources%sfc_source_Jac)) &
         call ccpp_capture('sfc_source_Jac', obj%sources%sfc_source_Jac, dim_names=dims_sfc)
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_sources_lw_write

   subroutine ccpp_capture_rte_sources_lw_read(group, name, obj)
      character(len=*),             intent(in)    :: group, name
      type(ty_source_func_lw_ccpp), intent(inout) :: obj
      character(len=:), allocatable :: path
      character(len=128) :: errmsg
      integer :: extents(3)
      logical :: initialized, found

      path = trim(group) // '/' // trim(name)
      call obj%sources%finalize()
      call read_spectral(path, obj%sources, initialized)
      if (.not. initialized) return
      call ccpp_capture_extents(path, 'lay_source', extents, found)
      if (.not. found) return
      errmsg = obj%sources%alloc(extents(1), extents(2))
      if (len_trim(errmsg) > 0) then
         call warn(path, errmsg)
         return
      end if
      call ccpp_capture_read(path, 'lay_source', obj%sources%lay_source)
      call ccpp_capture_read(path, 'lev_source', obj%sources%lev_source)
      call ccpp_capture_read(path, 'sfc_source', obj%sources%sfc_source)
      call ccpp_capture_read(path, 'sfc_source_Jac', obj%sources%sfc_source_Jac)
   end subroutine ccpp_capture_rte_sources_lw_read

   subroutine ccpp_capture_rte_sources_lw_compare(group, name, obj, tolerance, &
                                                  call_count, n_failed)
      character(len=*),             intent(in)    :: group, name
      type(ty_source_func_lw_ccpp), intent(in)    :: obj
      real(kind_phys),              intent(in)    :: tolerance
      integer,                      intent(in)    :: call_count
      integer,                      intent(inout) :: n_failed
      character(len=:), allocatable :: path

      path = trim(group) // '/' // trim(name)
      if (.not. compare_spectral(path, name, obj%sources, tolerance, call_count, &
                                 n_failed)) return
      call compare_alloc_3d(path, name, 'lay_source', tolerance, call_count, n_failed, &
                         obj%sources%lay_source)
      call compare_alloc_3d(path, name, 'lev_source', tolerance, call_count, n_failed, &
                         obj%sources%lev_source)
      call compare_alloc_2d(path, name, 'sfc_source', tolerance, call_count, n_failed, &
                         obj%sources%sfc_source)
      call compare_alloc_2d(path, name, 'sfc_source_Jac', tolerance, call_count, n_failed, &
                         obj%sources%sfc_source_Jac)
   end subroutine ccpp_capture_rte_sources_lw_compare

   ! ---------------------------------------------------------------------
   ! ty_fluxes_broadband_ccpp
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_fluxes_bb_write(name, obj)
      character(len=*),               intent(in) :: name
      type(ty_fluxes_broadband_ccpp), intent(in) :: obj

      call ccpp_capture_begin_ddt(name)
      call write_broadband(obj%fluxes)
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_fluxes_bb_write

   subroutine ccpp_capture_rte_fluxes_bb_read(group, name, obj)
      character(len=*),               intent(in)    :: group, name
      type(ty_fluxes_broadband_ccpp), intent(inout) :: obj

      call read_broadband(trim(group) // '/' // trim(name), obj%fluxes)
   end subroutine ccpp_capture_rte_fluxes_bb_read

   subroutine ccpp_capture_rte_fluxes_bb_compare(group, name, obj, tolerance, &
                                                 call_count, n_failed)
      character(len=*),               intent(in)    :: group, name
      type(ty_fluxes_broadband_ccpp), intent(in)    :: obj
      real(kind_phys),                intent(in)    :: tolerance
      integer,                        intent(in)    :: call_count
      integer,                        intent(inout) :: n_failed

      call compare_broadband(trim(group) // '/' // trim(name), name, obj%fluxes, &
                             tolerance, call_count, n_failed)
   end subroutine ccpp_capture_rte_fluxes_bb_compare

   ! ---------------------------------------------------------------------
   ! ty_fluxes_byband_ccpp
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_fluxes_byband_write(name, obj)
      character(len=*),            intent(in) :: name
      type(ty_fluxes_byband_ccpp), intent(in) :: obj

      call ccpp_capture_begin_ddt(name)
      call write_broadband(obj%fluxes)
      if (associated(obj%fluxes%bnd_flux_up)) &
         call ccpp_capture('bnd_flux_up', obj%fluxes%bnd_flux_up, dim_names=dims_bnd_flux)
      if (associated(obj%fluxes%bnd_flux_dn)) &
         call ccpp_capture('bnd_flux_dn', obj%fluxes%bnd_flux_dn, dim_names=dims_bnd_flux)
      if (associated(obj%fluxes%bnd_flux_net)) &
         call ccpp_capture('bnd_flux_net', obj%fluxes%bnd_flux_net, dim_names=dims_bnd_flux)
      if (associated(obj%fluxes%bnd_flux_dn_dir)) &
         call ccpp_capture('bnd_flux_dn_dir', obj%fluxes%bnd_flux_dn_dir, &
                           dim_names=dims_bnd_flux)
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_fluxes_byband_write

   subroutine ccpp_capture_rte_fluxes_byband_read(group, name, obj)
      character(len=*),            intent(in)    :: group, name
      type(ty_fluxes_byband_ccpp), intent(inout) :: obj
      character(len=:), allocatable :: path

      path = trim(group) // '/' // trim(name)
      call read_broadband(path, obj%fluxes)
      call read_pointer_3d(path, 'bnd_flux_up', obj%fluxes%bnd_flux_up)
      call read_pointer_3d(path, 'bnd_flux_dn', obj%fluxes%bnd_flux_dn)
      call read_pointer_3d(path, 'bnd_flux_net', obj%fluxes%bnd_flux_net)
      call read_pointer_3d(path, 'bnd_flux_dn_dir', obj%fluxes%bnd_flux_dn_dir)
   end subroutine ccpp_capture_rte_fluxes_byband_read

   subroutine ccpp_capture_rte_fluxes_byband_compare(group, name, obj, tolerance, &
                                                     call_count, n_failed)
      character(len=*),            intent(in)    :: group, name
      type(ty_fluxes_byband_ccpp), intent(in)    :: obj
      real(kind_phys),             intent(in)    :: tolerance
      integer,                     intent(in)    :: call_count
      integer,                     intent(inout) :: n_failed
      character(len=:), allocatable :: path

      path = trim(group) // '/' // trim(name)
      call compare_broadband(path, name, obj%fluxes, tolerance, call_count, n_failed)
      call compare_pointer_3d(path, name, 'bnd_flux_up', tolerance, call_count, n_failed, &
                         obj%fluxes%bnd_flux_up)
      call compare_pointer_3d(path, name, 'bnd_flux_dn', tolerance, call_count, n_failed, &
                         obj%fluxes%bnd_flux_dn)
      call compare_pointer_3d(path, name, 'bnd_flux_net', tolerance, call_count, n_failed, &
                         obj%fluxes%bnd_flux_net)
      call compare_pointer_3d(path, name, 'bnd_flux_dn_dir', tolerance, call_count, n_failed, &
                         obj%fluxes%bnd_flux_dn_dir)
   end subroutine ccpp_capture_rte_fluxes_byband_compare

   ! ---------------------------------------------------------------------
   ! ty_gas_concs_ccpp
   ! ---------------------------------------------------------------------
   ! Recorded: n_gases, gas_names, the shape the wrapper tracked (ncol,
   ! nlay; 0 = no such dimension), consistent (whether every set gas could
   ! be read back with that shape -- .false. means something set gas
   ! concentrations bypassing the wrapper), and vmr_<gas> for each gas whose
   ! concentration is set, as (max(ncol,1), max(nlay,1)).

   subroutine ccpp_capture_rte_gas_concs_write(name, obj)
      character(len=*),        intent(in) :: name
      type(ty_gas_concs_ccpp), intent(in) :: obj
      real(kind_phys), allocatable :: vmr(:,:)
      character(len=128) :: errmsg
      logical :: consistent, is_set
      integer :: n_gases, igas

      call ccpp_capture_begin_ddt(name)
      n_gases = gas_count(obj)
      call ccpp_capture('n_gases', n_gases)
      if (n_gases > 0) then
         call ccpp_capture('gas_names', obj%gas_concs%gas_names, dim_names=dims_gases)
         call ccpp_capture('ncol', obj%get_ncol())
         call ccpp_capture('nlay', obj%get_nlay())
         allocate(vmr(max(obj%get_ncol(), 1), max(obj%get_nlay(), 1)))
         consistent = .true.
         do igas = 1, n_gases
            call get_gas_vmr(obj, igas, vmr, is_set, errmsg)
            if (is_set) then
               call ccpp_capture(vmr_name(obj, igas), vmr, dim_names=dims_vmr)
            else if (len_trim(errmsg) > 0) then
               consistent = .false.
               call warn(name, errmsg)
            end if
         end do
         call ccpp_capture('consistent', consistent)
      end if
      call ccpp_capture_end_ddt()
   end subroutine ccpp_capture_rte_gas_concs_write

   ! Rebuild with init and set_vmr (the wrapper's, so its shape copy is
   ! rebuilt too), in the captured representation: 2-D when ncol > 0, a
   ! profile when only nlay > 0, a scalar otherwise.
   subroutine ccpp_capture_rte_gas_concs_read(group, name, obj)
      character(len=*),        intent(in)    :: group, name
      type(ty_gas_concs_ccpp), intent(inout) :: obj
      character(len=:), allocatable :: path
      character(len=gas_name_len), allocatable :: gas_names(:)
      real(kind_phys), allocatable :: vmr(:,:)
      character(len=128) :: errmsg
      integer :: n_gases, ncol, nlay, igas, extents(2)
      logical :: found

      path = trim(group) // '/' // trim(name)
      call obj%reset()
      call ccpp_capture_read(path, 'n_gases', n_gases, found)
      if (.not. found .or. n_gases <= 0) then
         ! No gases: still initialize (with none), so the object goes through
         ! RTE's init and its OpenACC enter data. RTE's final procedure
         ! deletes the object from the device, and a GPU driver crashed
         ! finalizing one that init never entered (an SW capture with no
         ! daylit columns).
         allocate(gas_names(0))
         errmsg = obj%init(gas_names)
         if (len_trim(errmsg) > 0) call warn(path, errmsg)
         return
      end if
      allocate(gas_names(n_gases))
      call ccpp_capture_read(path, 'gas_names', gas_names)
      call ccpp_capture_read(path, 'ncol', ncol)
      call ccpp_capture_read(path, 'nlay', nlay)
      errmsg = obj%init(gas_names)
      if (len_trim(errmsg) > 0) then
         call warn(path, errmsg)
         return
      end if
      do igas = 1, n_gases
         call ccpp_capture_extents(path, 'vmr_' // trim(gas_names(igas)), extents, found)
         if (.not. found) cycle
         allocate(vmr(extents(1), extents(2)))
         call ccpp_capture_read(path, 'vmr_' // trim(gas_names(igas)), vmr)
         if (ncol > 0) then
            errmsg = obj%set_vmr(trim(gas_names(igas)), vmr)
         else if (nlay > 0) then
            errmsg = obj%set_vmr(trim(gas_names(igas)), vmr(1,:))
         else
            errmsg = obj%set_vmr(trim(gas_names(igas)), vmr(1,1))
         end if
         if (len_trim(errmsg) > 0) call warn(path, errmsg)
         deallocate(vmr)
      end do
   end subroutine ccpp_capture_rte_gas_concs_read

   subroutine ccpp_capture_rte_gas_concs_compare(group, name, obj, tolerance, &
                                                 call_count, n_failed)
      character(len=*),        intent(in)    :: group, name
      type(ty_gas_concs_ccpp), intent(in)    :: obj
      real(kind_phys),         intent(in)    :: tolerance
      integer,                 intent(in)    :: call_count
      integer,                 intent(inout) :: n_failed
      character(len=:), allocatable :: path
      character(len=gas_name_len), allocatable :: expected_names(:)
      real(kind_phys), allocatable :: vmr(:,:)
      character(len=128) :: errmsg
      integer :: n_gases, expected_int, igas
      logical :: found, ok, shape_ok, is_set, consistent

      path = trim(group) // '/' // trim(name)
      n_gases = gas_count(obj)
      call ccpp_capture_read(path, 'n_gases', expected_int, found)
      ok = found .and. expected_int == n_gases
      call ccpp_capture_report(trim(name) // '%n_gases', call_count, ok, n_failed)
      if (.not. ok .or. n_gases == 0) return
      allocate(expected_names(n_gases))
      call ccpp_capture_read(path, 'gas_names', expected_names, found)
      ok = found .and. ccpp_capture_compare(obj%gas_concs%gas_names, expected_names)
      call ccpp_capture_report(trim(name) // '%gas_names', call_count, ok, n_failed)
      if (.not. ok) return
      call ccpp_capture_read(path, 'ncol', expected_int, found)
      shape_ok = found .and. expected_int == obj%get_ncol()
      call ccpp_capture_report(trim(name) // '%ncol', call_count, shape_ok, n_failed)
      call ccpp_capture_read(path, 'nlay', expected_int, found)
      ok = found .and. expected_int == obj%get_nlay()
      call ccpp_capture_report(trim(name) // '%nlay', call_count, ok, n_failed)
      if (.not. (ok .and. shape_ok)) return
      allocate(vmr(max(obj%get_ncol(), 1), max(obj%get_nlay(), 1)))
      consistent = .true.
      do igas = 1, n_gases
         call get_gas_vmr(obj, igas, vmr, is_set, errmsg)
         if (is_set) then
            call compare_r8_2d(path, name, vmr_name(obj, igas), tolerance, call_count, &
                               n_failed, vmr)
         else
            if (len_trim(errmsg) > 0) then
               consistent = .false.
               call warn(path, errmsg)
            end if
            call compare_missing(path, name, vmr_name(obj, igas), 2, call_count, n_failed)
         end if
      end do
      call ccpp_capture_read(path, 'consistent', ok, found)
      ok = found .and. ok .and. consistent
      call ccpp_capture_report(trim(name) // '%consistent', call_count, ok, n_failed)
   end subroutine ccpp_capture_rte_gas_concs_compare

   integer function gas_count(obj)
      type(ty_gas_concs_ccpp), intent(in) :: obj

      gas_count = 0
      if (allocated(obj%gas_concs%gas_names)) gas_count = size(obj%gas_concs%gas_names)
   end function gas_count

   function vmr_name(obj, igas) result(vname)
      type(ty_gas_concs_ccpp), intent(in) :: obj
      integer,                 intent(in) :: igas
      character(len=:), allocatable :: vname

      vname = 'vmr_' // trim(obj%gas_concs%gas_names(igas))
   end function vmr_name

   ! Gas igas's concentration into vmr, shaped from the wrapper's copy.
   ! is_set: it was read; otherwise errmsg is empty when the gas is simply
   ! not set, and RRTMGP's error (e.g. a shape the wrapper's copy does not
   ! match) when not.
   subroutine get_gas_vmr(obj, igas, vmr, is_set, errmsg)
      type(ty_gas_concs_ccpp), intent(in)  :: obj
      integer,                 intent(in)  :: igas
      real(kind_phys),         intent(out) :: vmr(:,:)
      logical,                 intent(out) :: is_set
      character(len=128),      intent(out) :: errmsg

      errmsg = obj%gas_concs%get_vmr(trim(obj%gas_concs%gas_names(igas)), vmr)
      is_set = len_trim(errmsg) == 0
      if (index(errmsg, "hasn't been set") > 0) errmsg = ''
   end subroutine get_gas_vmr

   ! ---------------------------------------------------------------------
   ! Device residency (GPU test drivers)
   ! ---------------------------------------------------------------------

   subroutine ccpp_capture_rte_props_1scl_device_enter(obj)
      type(ty_optical_props_1scl_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%optical_props)
      if (allocated(obj%optical_props%tau)) then
         !$acc enter data copyin(obj%optical_props%tau)
      end if
   end subroutine ccpp_capture_rte_props_1scl_device_enter

   subroutine ccpp_capture_rte_props_1scl_device_exit(obj, copy_out)
      type(ty_optical_props_1scl_ccpp), intent(inout) :: obj
      logical,                          intent(in)    :: copy_out

      if (allocated(obj%optical_props%tau)) then
         if (copy_out) then
            !$acc exit data copyout(obj%optical_props%tau)
         else
            !$acc exit data delete(obj%optical_props%tau)
         end if
      end if
      !$acc exit data delete(obj%optical_props)
   end subroutine ccpp_capture_rte_props_1scl_device_exit

   subroutine ccpp_capture_rte_props_2str_device_enter(obj)
      type(ty_optical_props_2str_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%optical_props)
      if (allocated(obj%optical_props%tau)) then
         !$acc enter data copyin(obj%optical_props%tau)
      end if
      if (allocated(obj%optical_props%ssa)) then
         !$acc enter data copyin(obj%optical_props%ssa)
      end if
      if (allocated(obj%optical_props%g)) then
         !$acc enter data copyin(obj%optical_props%g)
      end if
   end subroutine ccpp_capture_rte_props_2str_device_enter

   subroutine ccpp_capture_rte_props_2str_device_exit(obj, copy_out)
      type(ty_optical_props_2str_ccpp), intent(inout) :: obj
      logical,                          intent(in)    :: copy_out

      if (allocated(obj%optical_props%tau)) then
         if (copy_out) then
            !$acc exit data copyout(obj%optical_props%tau)
         else
            !$acc exit data delete(obj%optical_props%tau)
         end if
      end if
      if (allocated(obj%optical_props%ssa)) then
         if (copy_out) then
            !$acc exit data copyout(obj%optical_props%ssa)
         else
            !$acc exit data delete(obj%optical_props%ssa)
         end if
      end if
      if (allocated(obj%optical_props%g)) then
         if (copy_out) then
            !$acc exit data copyout(obj%optical_props%g)
         else
            !$acc exit data delete(obj%optical_props%g)
         end if
      end if
      !$acc exit data delete(obj%optical_props)
   end subroutine ccpp_capture_rte_props_2str_device_exit

   subroutine ccpp_capture_rte_sources_lw_device_enter(obj)
      type(ty_source_func_lw_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%sources)
      if (allocated(obj%sources%lay_source)) then
         !$acc enter data copyin(obj%sources%lay_source)
      end if
      if (allocated(obj%sources%lev_source)) then
         !$acc enter data copyin(obj%sources%lev_source)
      end if
      if (allocated(obj%sources%sfc_source)) then
         !$acc enter data copyin(obj%sources%sfc_source)
      end if
      if (allocated(obj%sources%sfc_source_Jac)) then
         !$acc enter data copyin(obj%sources%sfc_source_Jac)
      end if
   end subroutine ccpp_capture_rte_sources_lw_device_enter

   subroutine ccpp_capture_rte_sources_lw_device_exit(obj, copy_out)
      type(ty_source_func_lw_ccpp), intent(inout) :: obj
      logical,                      intent(in)    :: copy_out

      if (allocated(obj%sources%lay_source)) then
         if (copy_out) then
            !$acc exit data copyout(obj%sources%lay_source)
         else
            !$acc exit data delete(obj%sources%lay_source)
         end if
      end if
      if (allocated(obj%sources%lev_source)) then
         if (copy_out) then
            !$acc exit data copyout(obj%sources%lev_source)
         else
            !$acc exit data delete(obj%sources%lev_source)
         end if
      end if
      if (allocated(obj%sources%sfc_source)) then
         if (copy_out) then
            !$acc exit data copyout(obj%sources%sfc_source)
         else
            !$acc exit data delete(obj%sources%sfc_source)
         end if
      end if
      if (allocated(obj%sources%sfc_source_Jac)) then
         if (copy_out) then
            !$acc exit data copyout(obj%sources%sfc_source_Jac)
         else
            !$acc exit data delete(obj%sources%sfc_source_Jac)
         end if
      end if
      !$acc exit data delete(obj%sources)
   end subroutine ccpp_capture_rte_sources_lw_device_exit

   subroutine ccpp_capture_rte_fluxes_bb_device_enter(obj)
      type(ty_fluxes_broadband_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%fluxes)
      call broadband_device_enter(obj%fluxes)
   end subroutine ccpp_capture_rte_fluxes_bb_device_enter

   subroutine ccpp_capture_rte_fluxes_bb_device_exit(obj, copy_out)
      type(ty_fluxes_broadband_ccpp), intent(inout) :: obj
      logical,                        intent(in)    :: copy_out

      call broadband_device_exit(obj%fluxes, copy_out)
      !$acc exit data delete(obj%fluxes)
   end subroutine ccpp_capture_rte_fluxes_bb_device_exit

   subroutine ccpp_capture_rte_fluxes_byband_device_enter(obj)
      type(ty_fluxes_byband_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%fluxes)
      call broadband_device_enter(obj%fluxes)
      if (associated(obj%fluxes%bnd_flux_up)) then
         !$acc enter data copyin(obj%fluxes%bnd_flux_up)
      end if
      if (associated(obj%fluxes%bnd_flux_dn)) then
         !$acc enter data copyin(obj%fluxes%bnd_flux_dn)
      end if
      if (associated(obj%fluxes%bnd_flux_net)) then
         !$acc enter data copyin(obj%fluxes%bnd_flux_net)
      end if
      if (associated(obj%fluxes%bnd_flux_dn_dir)) then
         !$acc enter data copyin(obj%fluxes%bnd_flux_dn_dir)
      end if
   end subroutine ccpp_capture_rte_fluxes_byband_device_enter

   subroutine ccpp_capture_rte_fluxes_byband_device_exit(obj, copy_out)
      type(ty_fluxes_byband_ccpp), intent(inout) :: obj
      logical,                     intent(in)    :: copy_out

      if (associated(obj%fluxes%bnd_flux_up)) then
         if (copy_out) then
            !$acc exit data copyout(obj%fluxes%bnd_flux_up)
         else
            !$acc exit data delete(obj%fluxes%bnd_flux_up)
         end if
      end if
      if (associated(obj%fluxes%bnd_flux_dn)) then
         if (copy_out) then
            !$acc exit data copyout(obj%fluxes%bnd_flux_dn)
         else
            !$acc exit data delete(obj%fluxes%bnd_flux_dn)
         end if
      end if
      if (associated(obj%fluxes%bnd_flux_net)) then
         if (copy_out) then
            !$acc exit data copyout(obj%fluxes%bnd_flux_net)
         else
            !$acc exit data delete(obj%fluxes%bnd_flux_net)
         end if
      end if
      if (associated(obj%fluxes%bnd_flux_dn_dir)) then
         if (copy_out) then
            !$acc exit data copyout(obj%fluxes%bnd_flux_dn_dir)
         else
            !$acc exit data delete(obj%fluxes%bnd_flux_dn_dir)
         end if
      end if
      call broadband_device_exit(obj%fluxes, copy_out)
      !$acc exit data delete(obj%fluxes)
   end subroutine ccpp_capture_rte_fluxes_byband_device_exit

   subroutine ccpp_capture_rte_gas_concs_device_enter(obj)
      type(ty_gas_concs_ccpp), intent(inout) :: obj

      !$acc enter data copyin(obj%gas_concs)
   end subroutine ccpp_capture_rte_gas_concs_device_enter

   subroutine ccpp_capture_rte_gas_concs_device_exit(obj, copy_out)
      type(ty_gas_concs_ccpp), intent(inout) :: obj
      logical,                 intent(in)    :: copy_out

      ! Nothing of it is copied back: its contents stay on the host (RTE
      ! copies the concentrations it needs itself).
      if (copy_out) continue
      !$acc exit data delete(obj%gas_concs)
   end subroutine ccpp_capture_rte_gas_concs_device_exit

   ! The broadband flux arrays (pointers) of an object already on the device.
   subroutine broadband_device_enter(fluxes)
      class(ty_fluxes_broadband), intent(inout) :: fluxes

      if (associated(fluxes%flux_up)) then
         !$acc enter data copyin(fluxes%flux_up)
      end if
      if (associated(fluxes%flux_dn)) then
         !$acc enter data copyin(fluxes%flux_dn)
      end if
      if (associated(fluxes%flux_net)) then
         !$acc enter data copyin(fluxes%flux_net)
      end if
      if (associated(fluxes%flux_dn_dir)) then
         !$acc enter data copyin(fluxes%flux_dn_dir)
      end if
   end subroutine broadband_device_enter

   subroutine broadband_device_exit(fluxes, copy_out)
      class(ty_fluxes_broadband), intent(inout) :: fluxes
      logical,                    intent(in)    :: copy_out

      if (associated(fluxes%flux_up)) then
         if (copy_out) then
            !$acc exit data copyout(fluxes%flux_up)
         else
            !$acc exit data delete(fluxes%flux_up)
         end if
      end if
      if (associated(fluxes%flux_dn)) then
         if (copy_out) then
            !$acc exit data copyout(fluxes%flux_dn)
         else
            !$acc exit data delete(fluxes%flux_dn)
         end if
      end if
      if (associated(fluxes%flux_net)) then
         if (copy_out) then
            !$acc exit data copyout(fluxes%flux_net)
         else
            !$acc exit data delete(fluxes%flux_net)
         end if
      end if
      if (associated(fluxes%flux_dn_dir)) then
         if (copy_out) then
            !$acc exit data copyout(fluxes%flux_dn_dir)
         else
            !$acc exit data delete(fluxes%flux_dn_dir)
         end if
      end if
   end subroutine broadband_device_exit

   ! ---------------------------------------------------------------------
   ! Shared parts
   ! ---------------------------------------------------------------------

   ! The spectral discretization (ty_optical_props).
   subroutine write_spectral(props)
      class(ty_optical_props), intent(in) :: props

      call ccpp_capture('initialized', props%is_initialized())
      if (.not. props%is_initialized()) return
      call ccpp_capture('band_lims_wvn', props%get_band_lims_wavenumber(), dim_names=dims_band)
      call ccpp_capture('band_lims_gpt', props%get_band_lims_gpoint(), dim_names=dims_band)
      call ccpp_capture('name', trim(props%get_name()))
   end subroutine write_spectral

   ! Rebuild the spectral discretization of *props* (finalized by the
   ! caller) from *path*; *initialized* is whether it was initialized.
   subroutine read_spectral(path, props, initialized)
      character(len=*),        intent(in)    :: path
      class(ty_optical_props), intent(inout) :: props
      logical,                 intent(out)   :: initialized
      real(kind_phys), allocatable :: band_lims_wvn(:,:)
      integer, allocatable :: band_lims_gpt(:,:)
      character(len=name_len) :: props_name
      character(len=128) :: errmsg
      integer :: extents(2)
      logical :: found

      initialized = .false.
      call ccpp_capture_read(path, 'initialized', initialized, found)
      if (.not. found) initialized = .false.
      if (.not. initialized) return
      call ccpp_capture_extents(path, 'band_lims_wvn', extents, found)
      allocate(band_lims_wvn(extents(1), extents(2)), band_lims_gpt(extents(1), extents(2)))
      call ccpp_capture_read(path, 'band_lims_wvn', band_lims_wvn)
      call ccpp_capture_read(path, 'band_lims_gpt', band_lims_gpt)
      call ccpp_capture_read(path, 'name', props_name, found)
      errmsg = props%init(band_lims_wvn, band_lims_gpt, trim(props_name))
      if (len_trim(errmsg) > 0) then
         call warn(path, errmsg)
         initialized = .false.
      end if
   end subroutine read_spectral

   ! Compare the spectral discretization; .true. when both sides are
   ! initialized (so the arrays are worth comparing).
   logical function compare_spectral(path, label, props, tolerance, call_count, n_failed)
      character(len=*),        intent(in)    :: path, label
      class(ty_optical_props), intent(in)    :: props
      real(kind_phys),         intent(in)    :: tolerance
      integer,                 intent(in)    :: call_count
      integer,                 intent(inout) :: n_failed
      character(len=name_len) :: expected_name
      logical :: expected, found, ok

      compare_spectral = .false.
      expected = .false.
      call ccpp_capture_read(path, 'initialized', expected, found)
      ok = found .and. (expected .eqv. props%is_initialized())
      call ccpp_capture_report(trim(label) // '%initialized', call_count, ok, n_failed)
      if (.not. (ok .and. expected)) return
      call compare_r8_2d(path, label, 'band_lims_wvn', tolerance, call_count, n_failed, &
                         props%get_band_lims_wavenumber())
      call compare_int_2d(path, label, 'band_lims_gpt', call_count, n_failed, &
                          props%get_band_lims_gpoint())
      call ccpp_capture_read(path, 'name', expected_name, found)
      ok = found .and. (trim(expected_name) == trim(props%get_name()))
      call ccpp_capture_report(trim(label) // '%name', call_count, ok, n_failed)
      compare_spectral = .true.
   end function compare_spectral

   subroutine write_arry(props)
      class(ty_optical_props_arry), intent(in) :: props

      call write_spectral(props)
      if (.not. allocated(props%tau)) return
      call ccpp_capture('tau', props%tau, dim_names=dims_gpt3)
      call ccpp_capture('top_at_1', props%top_is_at_1())
      select type (props)
      type is (ty_optical_props_2str)
         if (allocated(props%ssa)) call ccpp_capture('ssa', props%ssa, dim_names=dims_gpt3)
         if (allocated(props%g)) call ccpp_capture('g', props%g, dim_names=dims_gpt3)
      end select
   end subroutine write_arry

   subroutine read_arry(path, props)
      character(len=*),             intent(in)    :: path
      class(ty_optical_props_arry), intent(inout) :: props
      character(len=128) :: errmsg
      integer :: extents(3)
      logical :: initialized, found, top_at_1

      errmsg = ''
      select type (props)
      type is (ty_optical_props_1scl)
         errmsg = props%finalize_1scl()
      type is (ty_optical_props_2str)
         errmsg = props%finalize_2str()
      end select
      call props%finalize()
      call read_spectral(path, props, initialized)
      if (.not. initialized) return
      call ccpp_capture_extents(path, 'tau', extents, found)
      if (.not. found) return
      select type (props)
      type is (ty_optical_props_1scl)
         errmsg = props%alloc_1scl(extents(1), extents(2))
      type is (ty_optical_props_2str)
         errmsg = props%alloc_2str(extents(1), extents(2))
      end select
      if (len_trim(errmsg) > 0) then
         call warn(path, errmsg)
         return
      end if
      call ccpp_capture_read(path, 'tau', props%tau)
      select type (props)
      type is (ty_optical_props_2str)
         call ccpp_capture_read(path, 'ssa', props%ssa)
         call ccpp_capture_read(path, 'g', props%g)
      end select
      call ccpp_capture_read(path, 'top_at_1', top_at_1, found)
      if (found) call props%set_top_at_1(top_at_1)
   end subroutine read_arry

   subroutine compare_arry(path, label, props, tolerance, call_count, n_failed)
      character(len=*),             intent(in)    :: path, label
      class(ty_optical_props_arry), intent(in)    :: props
      real(kind_phys),              intent(in)    :: tolerance
      integer,                      intent(in)    :: call_count
      integer,                      intent(inout) :: n_failed
      logical :: expected, found, ok

      if (.not. compare_spectral(path, label, props, tolerance, call_count, n_failed)) return
      call compare_alloc_3d(path, label, 'tau', tolerance, call_count, n_failed, props%tau)
      if (allocated(props%tau)) then
         call ccpp_capture_read(path, 'top_at_1', expected, found)
         ok = found .and. (expected .eqv. props%top_is_at_1())
         call ccpp_capture_report(trim(label) // '%top_at_1', call_count, ok, n_failed)
      end if
      select type (props)
      type is (ty_optical_props_2str)
         call compare_alloc_3d(path, label, 'ssa', tolerance, call_count, n_failed, props%ssa)
         call compare_alloc_3d(path, label, 'g', tolerance, call_count, n_failed, props%g)
      end select
   end subroutine compare_arry

   subroutine write_broadband(fluxes)
      class(ty_fluxes_broadband), intent(in) :: fluxes

      if (associated(fluxes%flux_up)) &
         call ccpp_capture('flux_up', fluxes%flux_up, dim_names=dims_flux)
      if (associated(fluxes%flux_dn)) &
         call ccpp_capture('flux_dn', fluxes%flux_dn, dim_names=dims_flux)
      if (associated(fluxes%flux_net)) &
         call ccpp_capture('flux_net', fluxes%flux_net, dim_names=dims_flux)
      if (associated(fluxes%flux_dn_dir)) &
         call ccpp_capture('flux_dn_dir', fluxes%flux_dn_dir, dim_names=dims_flux)
   end subroutine write_broadband

   subroutine read_broadband(path, fluxes)
      character(len=*),           intent(in)    :: path
      class(ty_fluxes_broadband), intent(inout) :: fluxes

      call read_pointer_2d(path, 'flux_up', fluxes%flux_up)
      call read_pointer_2d(path, 'flux_dn', fluxes%flux_dn)
      call read_pointer_2d(path, 'flux_net', fluxes%flux_net)
      call read_pointer_2d(path, 'flux_dn_dir', fluxes%flux_dn_dir)
   end subroutine read_broadband

   subroutine compare_broadband(path, label, fluxes, tolerance, call_count, n_failed)
      character(len=*),           intent(in)    :: path, label
      class(ty_fluxes_broadband), intent(in)    :: fluxes
      real(kind_phys),            intent(in)    :: tolerance
      integer,                    intent(in)    :: call_count
      integer,                    intent(inout) :: n_failed

      call compare_pointer_2d(path, label, 'flux_up', tolerance, call_count, n_failed, &
                         fluxes%flux_up)
      call compare_pointer_2d(path, label, 'flux_dn', tolerance, call_count, n_failed, &
                         fluxes%flux_dn)
      call compare_pointer_2d(path, label, 'flux_net', tolerance, call_count, n_failed, &
                         fluxes%flux_net)
      call compare_pointer_2d(path, label, 'flux_dn_dir', tolerance, call_count, n_failed, &
                         fluxes%flux_dn_dir)
   end subroutine compare_broadband

   ! A flux pointer: a new array with the captured values, or null.
   subroutine read_pointer_2d(path, comp, ptr)
      character(len=*),         intent(in) :: path, comp
      real(kind_phys), pointer, intent(inout) :: ptr(:,:)
      integer :: extents(2)
      logical :: found

      nullify(ptr)
      call ccpp_capture_extents(path, comp, extents, found)
      if (.not. found) return
      allocate(ptr(extents(1), extents(2)))
      call ccpp_capture_read(path, comp, ptr)
   end subroutine read_pointer_2d

   subroutine read_pointer_3d(path, comp, ptr)
      character(len=*),         intent(in) :: path, comp
      real(kind_phys), pointer, intent(inout) :: ptr(:,:,:)
      integer :: extents(3)
      logical :: found

      nullify(ptr)
      call ccpp_capture_extents(path, comp, extents, found)
      if (.not. found) return
      allocate(ptr(extents(1), extents(2), extents(3)))
      call ccpp_capture_read(path, comp, ptr)
   end subroutine read_pointer_3d

   ! Compare part *comp* with its captured value: an allocatable array or a
   ! pointer through the wrappers, which report a part present on one side
   ! only (unallocated / null after the call, or not captured) as a
   ! failure and say nothing when it is absent on both.
   subroutine compare_alloc_2d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*),             intent(in)    :: path, label, comp
      real(kind_phys),              intent(in)    :: tolerance
      integer,                      intent(in)    :: call_count
      integer,                      intent(inout) :: n_failed
      real(kind_phys), allocatable, intent(in)    :: actual(:,:)

      if (allocated(actual)) then
         call compare_r8_2d(path, label, comp, tolerance, call_count, n_failed, actual)
      else
         call compare_missing(path, label, comp, 2, call_count, n_failed)
      end if
   end subroutine compare_alloc_2d

   subroutine compare_alloc_3d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*),             intent(in)    :: path, label, comp
      real(kind_phys),              intent(in)    :: tolerance
      integer,                      intent(in)    :: call_count
      integer,                      intent(inout) :: n_failed
      real(kind_phys), allocatable, intent(in)    :: actual(:,:,:)

      if (allocated(actual)) then
         call compare_r8_3d(path, label, comp, tolerance, call_count, n_failed, actual)
      else
         call compare_missing(path, label, comp, 3, call_count, n_failed)
      end if
   end subroutine compare_alloc_3d

   subroutine compare_pointer_2d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*),         intent(in)    :: path, label, comp
      real(kind_phys),          intent(in)    :: tolerance
      integer,                  intent(in)    :: call_count
      integer,                  intent(inout) :: n_failed
      real(kind_phys), pointer, intent(in)    :: actual(:,:)

      if (associated(actual)) then
         call compare_r8_2d(path, label, comp, tolerance, call_count, n_failed, actual)
      else
         call compare_missing(path, label, comp, 2, call_count, n_failed)
      end if
   end subroutine compare_pointer_2d

   subroutine compare_pointer_3d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*),         intent(in)    :: path, label, comp
      real(kind_phys),          intent(in)    :: tolerance
      integer,                  intent(in)    :: call_count
      integer,                  intent(inout) :: n_failed
      real(kind_phys), pointer, intent(in)    :: actual(:,:,:)

      if (associated(actual)) then
         call compare_r8_3d(path, label, comp, tolerance, call_count, n_failed, actual)
      else
         call compare_missing(path, label, comp, 3, call_count, n_failed)
      end if
   end subroutine compare_pointer_3d

   ! The object has no part *comp* (of rank *rank*) after the call: a
   ! failure when it was captured.
   subroutine compare_missing(path, label, comp, rank, call_count, n_failed)
      character(len=*), intent(in)    :: path, label, comp
      integer,          intent(in)    :: rank, call_count
      integer,          intent(inout) :: n_failed
      integer :: extents(rank)
      logical :: found

      call ccpp_capture_extents(path, comp, extents, found)
      if (.not. found) return
      write(*,*) '  ', trim(label), '%', comp, ': captured, but not allocated after the call'
      call ccpp_capture_report(trim(label) // '%' // comp, call_count, .false., n_failed)
   end subroutine compare_missing

   ! Why a real array differs: the maximum difference and the first
   ! mismatching element (column-major index into *actual*/*expected*,
   ! flattened), with both values and their bit patterns -- a difference
   ! too small to print (subnormals, signed zeros) still shows.
   subroutine report_mismatch(label, comp, max_abs_diff, first, actual, expected)
      use, intrinsic :: iso_fortran_env, only: int64
      character(len=*), intent(in) :: label, comp
      real(kind_phys),  intent(in) :: max_abs_diff
      integer,          intent(in) :: first
      real(kind_phys),  intent(in) :: actual(:), expected(:)

      write(*,'(4a,es24.16)') '  ', trim(label), '%', trim(comp) // ': max abs diff ', max_abs_diff
      if (first < 1 .or. first > size(actual)) return
      write(*,'(a,i0,2(a,es24.16,a,z16.16,a))') '    first mismatch at element ', first, &
         ': actual ', actual(first), ' (', transfer(actual(first), 0_int64), ')', &
         ', expected ', expected(first), ' (', transfer(expected(first), 0_int64), ')'
   end subroutine report_mismatch

   subroutine compare_r8_2d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*), intent(in)    :: path, label, comp
      real(kind_phys),  intent(in)    :: tolerance
      integer,          intent(in)    :: call_count
      integer,          intent(inout) :: n_failed
      real(kind_phys),  intent(in)    :: actual(:,:)
      real(kind_phys), allocatable :: expected(:,:)
      real(kind_phys) :: max_abs_diff
      integer :: first
      integer :: extents(2)
      logical :: found, ok

      call ccpp_capture_extents(path, comp, extents, found)
      ok = captured_with_shape(label, comp, found, shape(actual), extents)
      if (ok) then
         allocate(expected(extents(1), extents(2)))
         call ccpp_capture_read(path, comp, expected)
         ok = ccpp_capture_compare(actual, expected, tolerance, max_abs_diff=max_abs_diff, &
                                   first_mismatch_index=first)
         if (.not. ok) call report_mismatch(label, comp, max_abs_diff, first, &
                                            reshape(actual, [size(actual)]), &
                                            reshape(expected, [size(expected)]))
      end if
      call ccpp_capture_report(trim(label) // '%' // comp, call_count, ok, n_failed)
   end subroutine compare_r8_2d

   subroutine compare_r8_3d(path, label, comp, tolerance, call_count, n_failed, actual)
      character(len=*), intent(in)    :: path, label, comp
      real(kind_phys),  intent(in)    :: tolerance
      integer,          intent(in)    :: call_count
      integer,          intent(inout) :: n_failed
      real(kind_phys),  intent(in)    :: actual(:,:,:)
      real(kind_phys), allocatable :: expected(:,:,:)
      real(kind_phys) :: max_abs_diff
      integer :: first
      integer :: extents(3)
      logical :: found, ok

      call ccpp_capture_extents(path, comp, extents, found)
      ok = captured_with_shape(label, comp, found, shape(actual), extents)
      if (ok) then
         allocate(expected(extents(1), extents(2), extents(3)))
         call ccpp_capture_read(path, comp, expected)
         ok = ccpp_capture_compare(actual, expected, tolerance, max_abs_diff=max_abs_diff, &
                                   first_mismatch_index=first)
         if (.not. ok) call report_mismatch(label, comp, max_abs_diff, first, &
                                            reshape(actual, [size(actual)]), &
                                            reshape(expected, [size(expected)]))
      end if
      call ccpp_capture_report(trim(label) // '%' // comp, call_count, ok, n_failed)
   end subroutine compare_r8_3d

   subroutine compare_int_2d(path, label, comp, call_count, n_failed, actual)
      character(len=*), intent(in)    :: path, label, comp
      integer,          intent(in)    :: call_count
      integer,          intent(inout) :: n_failed
      integer,          intent(in)    :: actual(:,:)
      integer, allocatable :: expected(:,:)
      integer :: extents(2)
      logical :: found, ok

      call ccpp_capture_extents(path, comp, extents, found)
      ok = captured_with_shape(label, comp, found, shape(actual), extents)
      if (ok) then
         allocate(expected(extents(1), extents(2)))
         call ccpp_capture_read(path, comp, expected)
         ok = ccpp_capture_compare(actual, expected)
      end if
      call ccpp_capture_report(trim(label) // '%' // comp, call_count, ok, n_failed)
   end subroutine compare_int_2d

   ! Whether part *comp*, present in the object after the call, was
   ! captured with the same shape; says why not.
   logical function captured_with_shape(label, comp, found, actual_shape, captured_shape)
      character(len=*), intent(in) :: label, comp
      logical,          intent(in) :: found
      integer,          intent(in) :: actual_shape(:), captured_shape(:)

      captured_with_shape = .false.
      if (.not. found) then
         write(*,*) '  ', trim(label), '%', comp, ': allocated after the call, but not captured'
      else if (any(actual_shape /= captured_shape)) then
         write(*,*) '  ', trim(label), '%', comp, ': shape ', actual_shape, &
            ', captured ', captured_shape
      else
         captured_with_shape = .true.
      end if
   end function captured_with_shape

   subroutine warn(path, errmsg)
      character(len=*), intent(in) :: path, errmsg

      write(0,*) 'ccpp_capture_rte_objects: ', trim(path), ': ', trim(errmsg)
   end subroutine warn

end module ccpp_capture_rte_objects
