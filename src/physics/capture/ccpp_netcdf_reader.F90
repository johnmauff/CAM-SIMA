! Plain-NetCDF implementation of ccpp_io_reader for the xdsl_ccpp scheme
! I/O capture test drivers.
!
! In the model, CAM-SIMA's PIO reader (src/physics/utils/pio_reader.F90)
! implements ccpp_io_reader. The standalone test drivers have no PIO, so a
! scheme init that reads a file through ccpp_io_reader (the RRTMGP gas
! optics init loads its coefficient file this way) is replayed with this
! reader instead: same interface, same checks and error codes as the PIO
! reader, netcdf-fortran calls underneath.
!
! Only the capture build compiles this file (it is a `source` in
! capture_handlers.txt); it is not on the model build's Filepath.
!
! The get_var routines differ only in type and rank and are generated
! from one template; change the template, not a single routine.

module ccpp_netcdf_reader
   use ccpp_io_reader, only: abstract_netcdf_reader_t

   implicit none
   private

   public :: netcdf_reader_t

   ! Error codes (the PIO reader's values)
   integer, parameter :: inq_dim_len_err          = 2
   integer, parameter :: inq_var_id_err           = 3
   integer, parameter :: inq_var_info_err         = 4
   integer, parameter :: bad_var_rank_err         = 5
   integer, parameter :: get_var_err              = 7
   integer, parameter :: not_char_type_err        = 8
   integer, parameter :: file_not_open_err        = 9
   integer, parameter :: open_file_err            = 1
   integer, parameter :: mismatch_start_count_err = 11
   integer, parameter :: bad_subset_num_elem_err  = 12
   integer, parameter :: bad_subset_range_err     = 13

   integer, parameter :: path_len = 1024

   type, extends(abstract_netcdf_reader_t) :: netcdf_reader_t
      private
      logical                 :: is_file_open = .false.
      integer                 :: ncid         = -1
      character(len=path_len) :: file_path    = 'UNSET'
   contains
      procedure :: open_file       => open_netcdf_file
      procedure :: close_file      => close_netcdf_file

      procedure :: get_var_int_0d => get_netcdf_var_int_0d
      procedure :: get_var_int_1d => get_netcdf_var_int_1d
      procedure :: get_var_int_2d => get_netcdf_var_int_2d
      procedure :: get_var_int_3d => get_netcdf_var_int_3d
      procedure :: get_var_int_4d => get_netcdf_var_int_4d
      procedure :: get_var_int_5d => get_netcdf_var_int_5d

      procedure :: get_var_real_0d => get_netcdf_var_real_0d
      procedure :: get_var_real_1d => get_netcdf_var_real_1d
      procedure :: get_var_real_2d => get_netcdf_var_real_2d
      procedure :: get_var_real_3d => get_netcdf_var_real_3d
      procedure :: get_var_real_4d => get_netcdf_var_real_4d
      procedure :: get_var_real_5d => get_netcdf_var_real_5d

      procedure :: get_var_char_0d => get_netcdf_var_char_0d
      procedure :: get_var_char_1d => get_netcdf_var_char_1d
      procedure :: get_var_char_2d => get_netcdf_var_char_2d
      procedure :: get_var_char_3d => get_netcdf_var_char_3d
      procedure :: get_var_char_4d => get_netcdf_var_char_4d
      procedure :: get_var_char_5d => get_netcdf_var_char_5d
   end type netcdf_reader_t

contains

   subroutine open_netcdf_file(this, file_path, errmsg, errcode)
      use netcdf, only: nf90_open, nf90_strerror, NF90_NOWRITE, NF90_NOERR

      class(netcdf_reader_t), intent(inout) :: this
      character(len=*),       intent(in)    :: file_path
      character(len=*),       intent(out)   :: errmsg
      integer,                intent(out)   :: errcode

      integer :: status

      if (this%is_file_open) then
         errcode = 1
         errmsg = "Trying to reuse netcdf_reader already used for: '"//trim(this%file_path)//"'"
         return
      end if

      status = nf90_open(file_path, NF90_NOWRITE, this%ncid)
      if (status /= NF90_NOERR) then
         errcode = open_file_err
         write(errmsg, '(4a)') "Error opening file '", trim(file_path), "' - message: ", &
            trim(nf90_strerror(status))
         return
      end if

      this%file_path    = file_path
      this%is_file_open = .true.
      errcode = 0
      errmsg = ''
   end subroutine open_netcdf_file

   subroutine close_netcdf_file(this, errmsg, errcode)
      use netcdf, only: nf90_close

      class(netcdf_reader_t), intent(inout) :: this
      character(len=*),       intent(out)   :: errmsg
      integer,                intent(out)   :: errcode

      integer :: status

      ! Like the PIO reader: closing a closed file is not an error
      if (this%is_file_open) then
         status = nf90_close(this%ncid)
         this%is_file_open = .false.
      end if
      errcode = 0
      errmsg = ''
   end subroutine close_netcdf_file

   ! ------------------------------------------------------------------
   ! Integer reads
   ! ------------------------------------------------------------------

   subroutine get_netcdf_var_int_0d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 0, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var, stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      status = nf90_get_var(this%ncid, var_id, var)
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_0d

   subroutine get_netcdf_var_int_1d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var(:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 1, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_1d

   subroutine get_netcdf_var_int_2d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var(:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 2, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_2d

   subroutine get_netcdf_var_int_3d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var(:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 3, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_3d

   subroutine get_netcdf_var_int_4d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var(:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 4, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3), alloc_dims(4)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_4d

   subroutine get_netcdf_var_int_5d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer, allocatable, intent(out) :: var(:,:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 5, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3), alloc_dims(4), alloc_dims(5)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_int_5d

   ! ------------------------------------------------------------------
   ! Real reads
   ! ------------------------------------------------------------------

   subroutine get_netcdf_var_real_0d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 0, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var, stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      status = nf90_get_var(this%ncid, var_id, var)
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_0d

   subroutine get_netcdf_var_real_1d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var(:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 1, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_1d

   subroutine get_netcdf_var_real_2d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var(:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 2, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_2d

   subroutine get_netcdf_var_real_3d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var(:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 3, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_3d

   subroutine get_netcdf_var_real_4d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var(:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 4, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3), alloc_dims(4)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_4d

   subroutine get_netcdf_var_real_5d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var
      use ccpp_kinds, only: kind_phys

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      real(kind_phys), allocatable, intent(out) :: var(:,:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 5, .false., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(var(alloc_dims(1), alloc_dims(2), alloc_dims(3), alloc_dims(4), alloc_dims(5)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = huge(1._kind_phys)

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_real_5d

   ! ------------------------------------------------------------------
   ! Character reads
   ! ------------------------------------------------------------------

   subroutine get_netcdf_var_char_0d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 1, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var, &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      status = nf90_get_var(this%ncid, var_id, var)
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_0d

   subroutine get_netcdf_var_char_1d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var(:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 2, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var(alloc_dims(2)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_1d

   subroutine get_netcdf_var_char_2d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var(:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 3, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var(alloc_dims(2), alloc_dims(3)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_2d

   subroutine get_netcdf_var_char_3d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var(:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 4, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var(alloc_dims(2), alloc_dims(3), alloc_dims(4)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_3d

   subroutine get_netcdf_var_char_4d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var(:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 5, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var(alloc_dims(2), alloc_dims(3), alloc_dims(4), alloc_dims(5)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_4d

   subroutine get_netcdf_var_char_5d(this, varname, var, errmsg, errcode, start, count)
      use netcdf, only: nf90_get_var

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      character(len=:), allocatable, intent(out) :: var(:,:,:,:,:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: var_id
      integer, allocatable :: alloc_dims(:)
      logical              :: do_subset
      integer              :: status

      call prepare_read(this, varname, 6, .true., var_id, alloc_dims, &
                        do_subset, errmsg, errcode, start, count)
      if (errcode /= 0) return

      allocate(character(alloc_dims(1)) :: var(alloc_dims(2), alloc_dims(3), alloc_dims(4), alloc_dims(5), alloc_dims(6)), &
               stat=errcode, errmsg=errmsg)
      if (errcode /= 0) return
      var = 'UNSET'

      if (do_subset) then
         status = nf90_get_var(this%ncid, var_id, var, start=start, count=count)
      else
         status = nf90_get_var(this%ncid, var_id, var)
      end if
      call read_status(status, varname, errmsg, errcode)
   end subroutine get_netcdf_var_char_5d

   ! ------------------------------------------------------------------
   ! Shared helpers
   ! ------------------------------------------------------------------

   subroutine prepare_read(this, varname, file_ndims, is_char, var_id, alloc_dims, &
                           do_subset, errmsg, errcode, start, count)
      ! Everything before the read: the file is open, the variable exists
      ! (a character array when is_char), has file_ndims dimensions on the
      ! file, and start/count are valid. alloc_dims is the shape to
      ! allocate, file order (for a character variable, the string length
      ! first). Scalars (file_ndims 0, or a character variable with only
      ! the string-length dimension) take no start/count.
      use netcdf, only: nf90_inq_varid, nf90_inquire_variable, NF90_CHAR, NF90_NOERR

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer,                intent(in)  :: file_ndims
      logical,                intent(in)  :: is_char
      integer,                intent(out) :: var_id
      integer, allocatable,   intent(out) :: alloc_dims(:)
      logical,                intent(out) :: do_subset
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode
      integer, optional,      intent(in)  :: start(:)
      integer, optional,      intent(in)  :: count(:)

      integer              :: status, nc_type
      integer, allocatable :: dim_sizes(:)
      logical              :: scalar

      errcode = 0
      errmsg = ''
      do_subset = .false.
      var_id = -1

      if (.not. this%is_file_open) then
         errcode = file_not_open_err
         errmsg = "File '"//trim(this%file_path)//"' is not open, need to call 'open_file' first."
         return
      end if

      status = nf90_inq_varid(this%ncid, varname, var_id)
      if (status /= NF90_NOERR) then
         call nc_errmsg(inq_var_id_err, varname, status, errmsg, errcode)
         return
      end if

      if (is_char) then
         status = nf90_inquire_variable(this%ncid, var_id, xtype=nc_type)
         if (status /= NF90_NOERR) then
            call nc_errmsg(inq_var_info_err, varname, status, errmsg, errcode)
            return
         end if
         if (nc_type /= NF90_CHAR) then
            errcode = not_char_type_err
            errmsg = "NetCDF Variable '"//trim(varname)// &
                     "' is not a character array.  File can be found here: "//trim(this%file_path)
            return
         end if
      end if

      call get_dim_sizes(this, varname, var_id, dim_sizes, errmsg, errcode)
      if (errcode /= 0) return

      if (size(dim_sizes) /= file_ndims) then
         errcode = bad_var_rank_err
         write(errmsg, '(4a,i0,a,i0,a)') &
            "Variable '", trim(varname), "' isn't declared with the correct number of dimensions.", &
            " Expected ", size(dim_sizes), " dimensions, but is declared with ", &
            file_ndims, " dimensions."
         return
      end if

      scalar = (file_ndims == 0) .or. (is_char .and. file_ndims == 1)
      if (scalar) then
         if (present(start) .or. present(count)) then
            errcode = bad_subset_num_elem_err
            errmsg = "Variable '"//trim(varname)// &
                     "' is a scalar variable, so start and count arguments must not be provided."
            return
         end if
         allocate(alloc_dims, source=dim_sizes)
         return
      end if

      call var_subset_check(varname, dim_sizes, do_subset, alloc_dims, errmsg, errcode, &
                            start, count)
   end subroutine prepare_read

   subroutine get_dim_sizes(this, varname, var_id, dim_sizes, errmsg, errcode)
      use netcdf, only: nf90_inquire_variable, nf90_inquire_dimension, NF90_NOERR

      class(netcdf_reader_t), intent(in)  :: this
      character(len=*),       intent(in)  :: varname
      integer,                intent(in)  :: var_id
      integer, allocatable,   intent(out) :: dim_sizes(:)
      character(len=*),       intent(out) :: errmsg
      integer,                intent(out) :: errcode

      integer              :: status, ndims, i
      integer, allocatable :: dim_ids(:)

      errcode = 0
      errmsg = ''
      status = nf90_inquire_variable(this%ncid, var_id, ndims=ndims)
      if (status /= NF90_NOERR) then
         call nc_errmsg(inq_var_info_err, varname, status, errmsg, errcode)
         return
      end if
      allocate(dim_ids(ndims), dim_sizes(ndims))
      if (ndims == 0) return
      status = nf90_inquire_variable(this%ncid, var_id, dimids=dim_ids)
      if (status /= NF90_NOERR) then
         call nc_errmsg(inq_var_info_err, varname, status, errmsg, errcode)
         return
      end if
      do i = 1, ndims
         status = nf90_inquire_dimension(this%ncid, dim_ids(i), len=dim_sizes(i))
         if (status /= NF90_NOERR) then
            call nc_errmsg(inq_dim_len_err, varname, status, errmsg, errcode)
            return
         end if
      end do
   end subroutine get_dim_sizes

   subroutine var_subset_check(varname, dim_sizes, do_subset, alloc_dims, errmsg, errcode, &
                               start, count)
      ! start and count both absent (whole variable) or both present, one
      ! element per file dimension, within bounds (the PIO reader's rules).
      character(len=*),     intent(in)  :: varname
      integer,              intent(in)  :: dim_sizes(:)
      logical,              intent(out) :: do_subset
      integer, allocatable, intent(out) :: alloc_dims(:)
      character(len=*),     intent(out) :: errmsg
      integer,              intent(out) :: errcode
      integer, optional,    intent(in)  :: start(:)
      integer, optional,    intent(in)  :: count(:)

      integer :: i, n

      errcode = 0
      errmsg = ''
      do_subset = .false.
      n = size(dim_sizes)

      if (.not. present(start) .and. .not. present(count)) then
         allocate(alloc_dims, source=dim_sizes)
         return
      end if
      if (.not. present(start)) then
         errcode = mismatch_start_count_err
         errmsg = "Variable '"//trim(varname)//"' is being subsetted with 'count', but no 'start' was provided."
         return
      else if (.not. present(count)) then
         errcode = mismatch_start_count_err
         errmsg = "Variable '"//trim(varname)//"' is being subsetted with 'start', but no 'count' was provided."
         return
      end if
      if (size(start) /= n) then
         errcode = bad_subset_num_elem_err
         write(errmsg, '(3a,i0,a,i0,a)') &
            "The number of elements in the 'start' array for variable '", trim(varname), &
            "' does not match the number of dimensions.  Expected ", n, " elements, but got ", &
            size(start), "."
         return
      end if
      if (size(count) /= n) then
         errcode = bad_subset_num_elem_err
         write(errmsg, '(3a,i0,a,i0,a)') &
            "The number of elements in the 'count' array for variable '", trim(varname), &
            "' does not match the number of dimensions.  Expected ", n, " elements, but got ", &
            size(count), "."
         return
      end if
      do i = 1, n
         if (start(i) < 1 .or. start(i) > dim_sizes(i)) then
            errcode = bad_subset_range_err
            write(errmsg, '(a,i0,3a,i0,a,i0,a)') "Element ", i, " of 'start' for variable '", &
               trim(varname), "' is out of bounds.  Expected 1 to ", dim_sizes(i), " but got ", &
               start(i), "."
            return
         end if
      end do
      do i = 1, n
         if (count(i) < 1 .or. start(i) + count(i) - 1 > dim_sizes(i)) then
            errcode = bad_subset_range_err
            write(errmsg, '(a,i0,3a,i0,a,i0,a)') "Element ", i, " of 'count' for variable '", &
               trim(varname), "' is out of bounds.  Expected 1 to ", dim_sizes(i) - start(i) + 1, &
               " but got ", count(i), "."
            return
         end if
      end do
      do_subset = .true.
      allocate(alloc_dims, source=count)
   end subroutine var_subset_check

   subroutine read_status(status, varname, errmsg, errcode)
      use netcdf, only: NF90_NOERR

      integer,          intent(in)  :: status
      character(len=*), intent(in)  :: varname
      character(len=*), intent(out) :: errmsg
      integer,          intent(out) :: errcode

      if (status /= NF90_NOERR) then
         call nc_errmsg(get_var_err, varname, status, errmsg, errcode)
      else
         errcode = 0
         errmsg = ''
      end if
   end subroutine read_status

   subroutine nc_errmsg(caller_errcode, varname, status, errmsg, errcode)
      use netcdf, only: nf90_strerror

      integer,          intent(in)  :: caller_errcode
      character(len=*), intent(in)  :: varname
      integer,          intent(in)  :: status
      character(len=*), intent(out) :: errmsg
      integer,          intent(out) :: errcode

      write(errmsg, '(4a)') "Error for variable '", trim(varname), "' - message: ", &
         trim(nf90_strerror(status))
      errcode = caller_errcode
   end subroutine nc_errmsg

end module ccpp_netcdf_reader

submodule (ccpp_io_reader) ccpp_netcdf_reader_sub
   ! The reader create_netcdf_reader_t returns in the capture test drivers
   ! (the model's is pio_reader_sub.F90).
   use ccpp_netcdf_reader, only: netcdf_reader_t
   implicit none
contains
   module procedure create_netcdf_reader_t
      allocate(netcdf_reader_t :: r)
   end procedure create_netcdf_reader_t
end submodule ccpp_netcdf_reader_sub
