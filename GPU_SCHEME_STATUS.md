# GPU status of the CAM physics schemes

Which schemes in the cam4, cam5 and cam7 suites
(`src/physics/ncar_ccpp/suites/suite_cam{4,5,7}.xml`) run on the GPU and are
confirmed bit-for-bit against the nvhpc CPU build.

- ✅ GPU-enabled and verified bit-for-bit on the GPU
- ❌ CPU only
- blank: the scheme is not in that configuration's suite
- 🧪 a unit test is available (a built capture replay of the scheme)

Generated 2026-11-13 by `tools/gpu_scheme_status.py`
(CAM-SIMA `e09d2ff`, atmospheric_physics `7663967`) from GPU
tests that passed bit-for-bit against their CPU baselines: xdsl84gpu
(33 cases). A scheme is ✅ when its own routines carry OpenACC
directives (or, for `micro_pumas_ccpp`, the package it calls runs on the GPU), its
object is compiled with OpenACC (`ccs_config/machines/Depends.nvhpc`), and it
runs in one of those tests. Verification is per scheme, so a scheme verified in
one suite is ✅ in every configuration that uses it; cam5 and cam7 marks can
come from the cam4 and FPHYStest runs.

| Scheme | cam4 | cam5 | cam7 |
|---|:---:|:---:|:---:|
| **Physics schemes** (✅ / schemes) | **49/108** | **47/97** | **41/88** |
| `aerosol_optics` | ❌ |  | ❌ |
| `apply_constituent_tendencies` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `apply_heating_rate` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `apply_tendency_of_air_temperature` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `apply_tendency_of_eastward_wind` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `apply_tendency_of_northward_wind` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `beljaars_add_wind_damping_rate` |  | ❌ |  |
| `beljaars_drag` |  | ✅ 🧪 | ✅ 🧪 |
| `bretherton_park_diff` |  | ❌ 🧪 |  |
| `calc_dry_air_ideal_gas_density` | ✅ 🧪 | ✅ 🧪 |  |
| `calculate_net_heating` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `check_energy_chng` | ❌ | ❌ | ❌ |
| `check_energy_fix` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `check_energy_gmean` | ❌ | ❌ | ❌ |
| `check_energy_save_teout` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `check_energy_scaling` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `check_energy_zero_fluxes` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `clamp_number_concentrations` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `cloud_condensate_floor` | ❌ | ❌ | ❌ |
| `cloud_fraction_fice` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `cloud_particle_sedimentation` | ❌ |  |  |
| `cloud_water_paths` | ❌ 🧪 | ❌ 🧪 | ❌ 🧪 |
| `compute_cloud_fraction` | ✅ 🧪 | ✅ 🧪 |  |
| `compute_cloud_fraction_two_moment` |  | ❌ | ❌ |
| `compute_kinematic_fluxes_and_obklen` | ❌ 🧪 | ❌ 🧪 |  |
| `compute_relative_humidity` |  |  | ❌ |
| `compute_subgrid_vertical_velocity_clubb` |  |  | ❌ 🧪 |
| `compute_subgrid_vertical_velocity_tke` |  | ❌ |  |
| `compute_total_precipitation_rate` |  |  | ❌ |
| `convect_shallow_sum_to_deep` | ✅ 🧪 |  |  |
| `convective_cloud_cover` | ✅ 🧪 |  |  |
| `convective_cloud_water` | ❌ 🧪 | ❌ 🧪 | ❌ 🧪 |
| `convert_dry_constituent_tendencies_to_dry_air_basis` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `dadadj` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `dropmixnuc_apply_surface_fluxes` |  | ✅ 🧪 |  |
| `dust_default_radii` |  | ❌ 🧪 | ❌ 🧪 |
| `dycore_energy_consistency_adjust` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `eddy_diffusivity_adjustment_above_pbl` |  | ✅ 🧪 |  |
| `geopotential_temp` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `gravity_wave_drag_common` | ❌ | ❌ | ❌ |
| `gravity_wave_drag_convection_deep` |  |  | ❌ |
| `gravity_wave_drag_frontogenesis` |  |  | ❌ |
| `gravity_wave_drag_moving_mountain` |  |  | ❌ |
| `gravity_wave_drag_orographic` | ❌ | ❌ |  |
| `gravity_wave_drag_prepare_profiles` | ❌ | ❌ | ❌ |
| `gravity_wave_drag_ridge_beta` |  |  | ❌ |
| `hack_convect_shallow` | ✅ 🧪 |  |  |
| `hb_diff_exchange_coefficients` | ✅ 🧪 |  |  |
| `hb_diff_prepare_vertical_diffusion_inputs` | ❌ | ❌ |  |
| `hb_pbl_dependent_coefficients` | ✅ 🧪 |  |  |
| `hb_pbl_independent_coefficients` | ✅ 🧪 |  |  |
| `implicit_surface_stress_add_drag_coefficient` | ❌ 🧪 | ❌ 🧪 |  |
| `mcsp` |  |  | ❌ |
| `micro_pumas_ccpp` ¹ |  | ✅ 🧪 | ✅ 🧪 |
| `micro_pumas_ccpp_dimensions_post` |  | ✅ 🧪 | ✅ 🧪 |
| `micro_pumas_ccpp_dimensions_pre` |  | ✅ 🧪 | ✅ 🧪 |
| `micro_pumas_ccpp_optics_limiter` |  | ✅ 🧪 | ✅ 🧪 |
| `ndrop_bam_ccpp` |  | ❌ | ❌ |
| `nucleate_ice_ccpp` |  | ❌ | ❌ |
| `prescribe_lower_boundary_conditions` | ❌ |  |  |
| `prescribe_radiative_gas_concentrations` | ❌ | ❌ | ❌ |
| `prescribe_radiative_gas_vertical_profiles` | ❌ |  |  |
| `prescribed_aerosol_deposition_flux` | ❌ |  | ❌ |
| `prescribed_aerosols` | ❌ | ❌ | ❌ |
| `prescribed_ozone` | ❌ | ❌ | ❌ |
| `prescribed_volcanic_aerosol` | ❌ |  | ❌ |
| `prognostic_cloud_water` | ❌ 🧪 |  |  |
| `pumas_post_main` |  | ✅ 🧪 | ✅ 🧪 |
| `qneg` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rebin_seasalt` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rk_stratiform_check_qtlcwat` | ❌ |  |  |
| `rk_stratiform_cloud_fraction_perturbation` | ❌ |  |  |
| `rk_stratiform_cloud_optical_properties` | ❌ |  |  |
| `rk_stratiform_condensate_repartioning` | ❌ |  |  |
| `rk_stratiform_detrain_convective_condensate` | ❌ |  |  |
| `rk_stratiform_external_forcings` | ❌ |  |  |
| `rk_stratiform_prepare_flux_for_check_energy` | ✅ 🧪 |  |  |
| `rk_stratiform_prognostic_cloud_water_tendencies` | ❌ |  |  |
| `rk_stratiform_pumas_optics_inputs` | ❌ |  |  |
| `rk_stratiform_save_qtlcwat` | ❌ |  |  |
| `rk_stratiform_sedimentation` | ❌ |  |  |
| `rrtmgp_constituents` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rrtmgp_dry_static_energy_tendency` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rrtmgp_inputs` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_aerosols` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_calculate_fluxes` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_calculate_heating_rate` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rrtmgp_lw_cloud_optics` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_gas_optics` | ✅ | ✅ | ✅ |
| `rrtmgp_lw_gas_optics_pre` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_mcica_subcol_gen` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_rte` | ✅ | ✅ | ✅ |
| `rrtmgp_post` | ❌ | ❌ | ❌ |
| `rrtmgp_pre` | ❌ | ❌ | ❌ |
| `rrtmgp_subcycle` | ❌ 🧪 | ❌ 🧪 | ❌ 🧪 |
| `rrtmgp_sw_aerosols` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_calculate_fluxes` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_calculate_heating_rate` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `rrtmgp_sw_cloud_optics` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_gas_optics` | ✅ | ✅ | ✅ |
| `rrtmgp_sw_gas_optics_pre` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_mcica_subcol_gen` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_rte` | ✅ | ✅ | ✅ |
| `rrtmgp_sw_solar_var` | ❌ | ❌ | ❌ |
| `rrtmgp_variables` | ❌ 🧪 | ❌ 🧪 | ❌ 🧪 |
| `save_core_tend_from_convect_deep` |  |  | ❌ |
| `save_ttend_from_convect_deep` |  |  | ❌ |
| `scale_subgrid_vertical_velocity` |  | ❌ 🧪 | ❌ 🧪 |
| `set_deep_conv_fluxes_to_general` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `set_general_conv_fluxes_to_deep` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `set_general_conv_fluxes_to_shallow` | ✅ 🧪 |  |  |
| `set_shallow_conv_fluxes_to_general` | ✅ 🧪 |  |  |
| `set_surface_coupling_vars` | ✅ 🧪 | ✅ 🧪 |  |
| `solar_irradiance_data` | ❌ | ❌ | ❌ |
| `tms_beljaars_zero_stub` | ✅ 🧪 |  |  |
| `tropopause_find` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `turbulent_mountain_stress_add_drag_coefficient` |  | ✅ 🧪 |  |
| `update_dry_static_energy` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `vertical_diffusion_diffuse_dry_static_energy` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_diffuse_horizontal_momentum` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_diffuse_tracers` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_interpolate_to_interfaces` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_prepare_inputs` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_set_dry_static_energy_at_toa_zero` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_set_temperature_at_toa_default` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_set_total_surface_stress` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_sponge_layer` | ✅ 🧪 | ✅ 🧪 |  |
| `vertical_diffusion_tendencies` | ❌ 🧪 | ❌ 🧪 |  |
| `vertical_diffusion_wind_damping_rate` | ❌ 🧪 | ❌ 🧪 |  |
| `wv_saturation` | ✅ | ✅ | ✅ |
| `zm_conv_cloud_top` |  |  | ❌ |
| `zm_conv_convtran` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `zm_conv_evap` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `zm_conv_momtran` | ✅ 🧪 | ✅ 🧪 | ✅ 🧪 |
| `zm_convr` | ❌ 🧪 | ❌ 🧪 | ❌ 🧪 |
| `zm_prepare_flux_for_check_energy` | ✅ 🧪 |  | ✅ 🧪 |
| **Register/init/final-only schemes** (✅ / schemes) | **0/13** | **0/13** | **0/12** |
| `cloud_fraction_options` | ❌ | ❌ | ❌ |
| `clubb_stub` |  |  | ❌ |
| `gravity_wave_drag_ridge` |  |  | ❌ |
| `gravity_wave_drag_top_taper` | ❌ | ❌ | ❌ |
| `hb_diff_set_vertical_diffusion_top` | ❌ | ❌ |  |
| `hetfrz_classnuc_stub` |  | ❌ | ❌ |
| `holtslag_boville_diff` | ❌ |  |  |
| `holtslag_boville_diff_options` | ❌ |  |  |
| `pumas_pre_main` |  | ❌ | ❌ |
| `rrtmgp_cloud_optics_setup` | ❌ | ❌ | ❌ |
| `rrtmgp_inputs_setup` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_solar_var_setup` | ❌ | ❌ | ❌ |
| `set_cloud_fraction_top` |  |  | ❌ |
| `to_be_ccppized_temporary` | ❌ | ❌ | ❌ |
| `vertical_diffusion_not_use_rairv` | ❌ | ❌ |  |
| `vertical_diffusion_options` | ❌ | ❌ |  |
| `zero_upper_boundary_condition` | ❌ | ❌ |  |
| `zm_conv_options` | ❌ | ❌ | ❌ |
| **Diagnostics schemes** (✅ / schemes) | **0/34** | **0/22** | **0/27** |
| `aerosol_optics_diagnostics` | ❌ |  | ❌ |
| `beljaars_drag_diagnostics` |  | ❌ | ❌ |
| `bretherton_park_diff_diagnostics` |  | ❌ |  |
| `check_energy_fix_diagnostics` |  |  | ❌ |
| `check_energy_gmean_diagnostics` | ❌ | ❌ | ❌ |
| `cloud_cover_diagnostics` | ❌ |  |  |
| `cloud_particle_sedimentation_diagnostics` | ❌ |  |  |
| `cloud_water_paths_diagnostics` | ❌ | ❌ | ❌ |
| `compute_cloud_fraction_diagnostics` | ❌ |  |  |
| `convect_shallow_diagnostics` | ❌ |  |  |
| `convect_shallow_diagnostics_after_convective_evaporation` | ❌ |  |  |
| `convect_shallow_diagnostics_after_shallow_scheme` | ❌ |  |  |
| `convect_shallow_diagnostics_after_sum_to_deep` | ❌ |  |  |
| `convective_cloud_cover_diagnostics` | ❌ |  |  |
| `convective_cloud_water_diagnostics` | ❌ | ❌ | ❌ |
| `gravity_wave_drag_common_diagnostics` | ❌ | ❌ | ❌ |
| `gravity_wave_drag_convection_deep_diagnostics` |  |  | ❌ |
| `gravity_wave_drag_frontogenesis_diagnostics` |  |  | ❌ |
| `gravity_wave_drag_moving_mountain_diagnostics` |  |  | ❌ |
| `gravity_wave_drag_orographic_diagnostics` | ❌ |  |  |
| `gravity_wave_drag_ridge_beta_diagnostics` |  |  | ❌ |
| `holtslag_boville_diff_diagnostics` | ❌ |  |  |
| `mcsp_diagnostics` |  |  | ❌ |
| `ndrop_bam_diagnostics` |  | ❌ | ❌ |
| `nucleate_ice_diagnostics` |  | ❌ | ❌ |
| `rk_stratiform_cloud_fraction_perturbation_diagnostics` | ❌ |  |  |
| `rk_stratiform_cloud_optical_properties_diagnostics` | ❌ |  |  |
| `rk_stratiform_condensate_repartioning_diagnostics` | ❌ |  |  |
| `rk_stratiform_diagnostics` | ❌ |  |  |
| `rk_stratiform_prognostic_cloud_water_tendencies_diagnostics` | ❌ |  |  |
| `rrtmgp_cloud_diagnostics` | ❌ | ❌ | ❌ |
| `rrtmgp_diagnostics` | ❌ | ❌ | ❌ |
| `rrtmgp_lw_diagnostics` | ❌ | ❌ | ❌ |
| `rrtmgp_sw_diagnostics` | ❌ | ❌ | ❌ |
| `scale_subgrid_vertical_velocity_diagnostics` |  | ❌ | ❌ |
| `sima_state_diagnostics` | ❌ | ❌ | ❌ |
| `sima_tend_diagnostics` | ❌ | ❌ | ❌ |
| `surface_coupling_diagnostics` | ❌ |  |  |
| `tropopause_diagnostics` | ❌ | ❌ | ❌ |
| `vertical_diffusion_tendencies_diagnostics` | ❌ | ❌ |  |
| `zm_convr_tendency_diagnostics` | ❌ | ❌ | ❌ |
| `zm_diagnostics` | ❌ | ❌ | ❌ |
| `zm_evap_tendency_diagnostics` | ❌ | ❌ | ❌ |
| `zm_momtran_tendency_diagnostics` | ❌ | ❌ | ❌ |
| `zm_tendency_diagnostics` | ❌ | ❌ | ❌ |

¹ No OpenACC in the CCPP wrapper itself; the package it calls runs on the GPU
and is verified bit-for-bit.

## Sections

- **Physics schemes**: schemes with per-timestep phases (timestep_init, run,
  timestep_final), and libraries: register/init/final-only schemes whose
  module holds routines other schemes call each timestep
  (`wv_saturation`'s `qsat_vect`, `gravity_wave_drag_common`'s
  `gw_drag_prof`) -- the GPU porting work.
- **Register/init/final-only schemes**: no per-timestep work; ❌ here rarely
  needs a port.
- **Diagnostics schemes**: write history output on the host.
