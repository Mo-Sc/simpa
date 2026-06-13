from simpa import Tags
import numpy as np
import simpa as sp
from config import segmentation_class_mapping


def _visualize_results(
    subject_id: str,
    wavelengths_nm: list,
    exp_id: int,
    melanin_volume_fraction: float | None = None,
    show_time_series: bool = False,
    show_reconstruction: bool = False,
):
    for wavelength_nm in wavelengths_nm:
        sp.visualise_data(
            path_to_hdf5_file=(
                sp.PathManager().get_hdf5_file_save_path() + "/" + subject_id + ".hdf5"
            ),
            wavelength=wavelength_nm,
            show_time_series_data=show_time_series,
            show_initial_pressure=True,
            show_segmentation_map=True,
            show_reconstructed_data=show_reconstruction,
            show_fluence=True,
            save_path=(
                sp.PathManager().get_hdf5_file_save_path()
                + "/"
                + f"{subject_id}_{wavelength_nm}_{exp_id}"
                + (
                    f"_rmelfrac_{melanin_volume_fraction}"
                    if melanin_volume_fraction is not None
                    else ""
                )
                + ".png"
            ),
        )


def _create_base_settings(
    subject_id: str,
    subject_data: dict,
    wavelengths_nm: list,
    pv_effects: bool = False,
):

    VOLUME_TRANSDUCER_DIM_IN_MM = (
        40  # xsize of recorded scan / seg mask. will be padded to transducer size
    )
    VOLUME_PLANAR_DIM_IN_MM = 15
    VOLUME_HEIGHT_IN_MM = 71.5  # z size of recorded scan / seg mask
    RANDOM_SEED = 471
    SPACING_MM = 0.1

    general_settings = {
        Tags.RANDOM_SEED: RANDOM_SEED,
        Tags.VOLUME_NAME: subject_id,
        Tags.SIMULATION_PATH: sp.PathManager().get_hdf5_file_save_path(),
        Tags.SIMPA_OUTPUT_FILE_PATH: sp.PathManager().get_hdf5_file_save_path()
        + "/"
        + subject_id
        + ".hdf5",
        Tags.SPACING_MM: SPACING_MM,
        Tags.DIM_VOLUME_Z_MM: VOLUME_HEIGHT_IN_MM,
        Tags.DIM_VOLUME_X_MM: VOLUME_TRANSDUCER_DIM_IN_MM,
        Tags.DIM_VOLUME_Y_MM: VOLUME_PLANAR_DIM_IN_MM,
        Tags.WAVELENGTHS: wavelengths_nm,
        Tags.GPU: True,
        Tags.IGNORE_QA_ASSERTIONS: False,
        Tags.DO_FILE_COMPRESSION: True,
        Tags.DO_IPASC_EXPORT: False,
        Tags.VOLUME_CREATOR: Tags.VOLUME_CREATOR_SEGMENTATION_BASED,
    }

    settings = sp.Settings(general_settings)

    settings.set_volume_creation_settings(
        {
            Tags.INPUT_SEGMENTATION_VOLUME: subject_data["seg_volume"],
            Tags.SEGMENTATION_CLASS_MAPPING: segmentation_class_mapping(subject_data),
            Tags.CONSIDER_PARTIAL_VOLUME: pv_effects,
        }
    )

    return settings


def _create_device(settings):

    VOLUME_TRANSDUCER_DIM_IN_MM = settings[Tags.DIM_VOLUME_X_MM]
    VOLUME_PLANAR_DIM_IN_MM = settings[Tags.DIM_VOLUME_Y_MM]

    device_position = np.array(
        [VOLUME_TRANSDUCER_DIM_IN_MM / 2, VOLUME_PLANAR_DIM_IN_MM / 2, 0]
    )

    # we only add 8 because we dont add a mediprene layer
    # so we only account for focus_in_field_of_view_mm, which is 8mm
    field_of_view_extent = np.array([-20.75, 20.75, 0, 0, -20.75 + 8, 20.75 + 8])

    device = sp.MSOTAcuityEcho(
        device_position_mm=device_position, field_of_view_extent_mm=field_of_view_extent
    )

    detection_geometry = sp.CurvedArrayDetectionGeometry(
        pitch_mm=0.34,
        radius_mm=40,
        number_detector_elements=256,
        detector_element_width_mm=0.24,
        detector_element_length_mm=13,
        center_frequency_hz=3.96e6,
        bandwidth_percent=153,  # modified compared to the default value of 55%
        sampling_frequency_mhz=40,
        angular_origin_offset=np.pi,
        device_position_mm=device_position,
        field_of_view_extent_mm=field_of_view_extent,
    )

    device.set_detection_geometry(detection_geometry)

    # no layers have to be added, membrane, heavy water, and us gel are already in the segmentation
    # therefore commented out in MSOTAcuityEcho device class
    # this should expand the volume to required dimensions for transducer by padding the segmentation
    device.update_settings_for_use_of_segmentation_based_volume_creator(settings)

    return device


def configure_optical(settings):

    LASER_ENERGY_MJ = np.array([11.25, 9.93, 6.5])
    N_PHOTONS = 1e7

    settings.set_optical_settings(
        {
            Tags.OPTICAL_MODEL_NUMBER_PHOTONS: N_PHOTONS,
            Tags.OPTICAL_MODEL_BINARY_PATH: sp.PathManager().get_mcx_binary_path(),
            Tags.ILLUMINATION_TYPE: Tags.ILLUMINATION_TYPE_MSOT_ACUITY_ECHO,
            Tags.LASER_PULSE_ENERGY_IN_MILLIJOULE: LASER_ENERGY_MJ,
            Tags.ADDITIONAL_FLAGS: ["--printgpu"],
        }
    )

    settings["noise_initial_pressure"] = {
        Tags.NOISE_MEAN: 1,
        Tags.NOISE_STD: 0.01,
        Tags.NOISE_MODE: Tags.NOISE_MODE_MULTIPLICATIVE,
        Tags.DATA_FIELD: Tags.DATA_FIELD_INITIAL_PRESSURE,
        Tags.NOISE_NON_NEGATIVITY_CONSTRAINT: True,
    }

    settings["FieldOfViewCropping"] = {
        Tags.DATA_FIELD: [
            Tags.DATA_FIELD_ALPHA_COEFF,
            Tags.DATA_FIELD_DENSITY,
            Tags.DATA_FIELD_ANISOTROPY,
            Tags.DATA_FIELD_GRUNEISEN_PARAMETER,
            Tags.DATA_FIELD_ABSORPTION_PER_CM,
            Tags.DATA_FIELD_SCATTERING_PER_CM,
            Tags.DATA_FIELD_SEGMENTATION,
            Tags.DATA_FIELD_SPEED_OF_SOUND,
            Tags.DATA_FIELD_FLUENCE,
        ]
    }


def configure_acoustic(settings):

    settings.set_acoustic_settings(
        {
            Tags.ACOUSTIC_SIMULATION_3D: True,
            Tags.ACOUSTIC_MODEL_BINARY_PATH: sp.PathManager().get_matlab_binary_path(),
            Tags.KWAVE_PROPERTY_ALPHA_POWER: 0.00,
            Tags.KWAVE_PROPERTY_SENSOR_RECORD: "p",
            Tags.KWAVE_PROPERTY_PMLInside: False,
            Tags.KWAVE_PROPERTY_PMLSize: [31, 32],
            Tags.KWAVE_PROPERTY_PMLAlpha: 1.5,
            Tags.KWAVE_PROPERTY_PlotPML: False,
            Tags.RECORDMOVIE: False,
            Tags.MOVIENAME: "visualization_log",
            Tags.ACOUSTIC_LOG_SCALE: True,
        }
    )

    settings["noise_time_series"] = {
        Tags.NOISE_STD: 1,
        Tags.NOISE_MODE: Tags.NOISE_MODE_ADDITIVE,
        Tags.DATA_FIELD: Tags.DATA_FIELD_TIME_SERIES_DATA,
    }

    settings.set_reconstruction_settings(
        {
            Tags.RECONSTRUCTION_PERFORM_BANDPASS_FILTERING: False,
            Tags.ACOUSTIC_MODEL_BINARY_PATH: sp.PathManager().get_matlab_binary_path(),
            Tags.ACOUSTIC_SIMULATION_3D: False,
            Tags.KWAVE_PROPERTY_ALPHA_POWER: 0.00,
            Tags.TUKEY_WINDOW_ALPHA: 0.5,
            Tags.BANDPASS_CUTOFF_LOWPASS_IN_HZ: int(8e6),
            Tags.BANDPASS_CUTOFF_HIGHPASS_IN_HZ: int(0.1e4),
            Tags.RECONSTRUCTION_BMODE_AFTER_RECONSTRUCTION: False,
            Tags.RECONSTRUCTION_BMODE_METHOD: Tags.RECONSTRUCTION_BMODE_METHOD_HILBERT_TRANSFORM,
            Tags.RECONSTRUCTION_APODIZATION_METHOD: Tags.RECONSTRUCTION_APODIZATION_BOX,
            Tags.RECONSTRUCTION_MODE: Tags.RECONSTRUCTION_MODE_PRESSURE,
            Tags.KWAVE_PROPERTY_SENSOR_RECORD: "p",
            Tags.KWAVE_PROPERTY_PMLInside: False,
            Tags.KWAVE_PROPERTY_PMLSize: [31, 32],
            Tags.KWAVE_PROPERTY_PMLAlpha: 1.5,
            Tags.KWAVE_PROPERTY_PlotPML: False,
            Tags.RECORDMOVIE: False,
            Tags.MOVIENAME: "visualization_log",
            Tags.ACOUSTIC_LOG_SCALE: True,
            Tags.DATA_FIELD_SPEED_OF_SOUND: 1540,
            Tags.DATA_FIELD_ALPHA_COEFF: 0.01,
            Tags.DATA_FIELD_DENSITY: 1000,
            Tags.SPACING_MM: settings[Tags.SPACING_MM],
        }
    )


# ============================================================
# PIPELINE RUN FUNCTIONS


def run_optical_simulation(
    exp_id,
    subject_id,
    subject_data,
    wavelengths_nm,
    pv_effects,
):
    """
    Runs only optical sim
    """

    settings = _create_base_settings(
        subject_id=subject_id,
        subject_data=subject_data,
        wavelengths_nm=wavelengths_nm,
        pv_effects=pv_effects,
    )

    device = _create_device(settings)

    configure_optical(settings)

    pipeline = [
        sp.SegmentationBasedAdapter(settings),
        sp.MCXAdapter(settings),
        sp.GaussianNoise(settings, "noise_initial_pressure"),
        sp.FieldOfViewCropping(settings),
    ]

    sp.simulate(pipeline, settings, device)

    _visualize_results(
        subject_id,
        wavelengths_nm,
        exp_id,
        melanin_volume_fraction=subject_data["melanin_fraction"],
        show_time_series=False,
        show_reconstruction=False,
    )


def run_optical_acoustic_simulation(
    exp_id, subject_id, subject_data, wavelengths_nm, pv_effects
):
    """
    Runs both the optical and acoustic simulation
    """

    settings = _create_base_settings(
        subject_id=subject_id,
        subject_data=subject_data,
        wavelengths_nm=wavelengths_nm,
        pv_effects=pv_effects,
    )

    device = _create_device(settings)

    configure_optical(settings)
    configure_acoustic(settings)

    pipeline = [
        sp.SegmentationBasedAdapter(settings),
        sp.MCXAdapter(settings),
        sp.GaussianNoise(settings, "noise_initial_pressure"),
        sp.KWaveAdapter(settings),
        sp.GaussianNoise(settings, "noise_time_series"),
        sp.TimeReversalAdapter(settings),
        sp.FieldOfViewCropping(settings),
    ]

    sp.simulate(pipeline, settings, device)

    # linear unmixing
    # settings["linear_unmixing"] = {
    #     # Tags.DATA_FIELD: Tags.DATA_FIELD_INITIAL_PRESSURE,
    #     Tags.DATA_FIELD: Tags.DATA_FIELD_RECONSTRUCTED_DATA,
    #     Tags.WAVELENGTHS: wavelengths_nm,
    #     Tags.LINEAR_UNMIXING_SPECTRA: sp.get_simpa_internal_absorption_spectra_by_names(
    #         [
    #             Tags.SIMPA_NAMED_ABSORPTION_SPECTRUM_OXYHEMOGLOBIN,
    #             Tags.SIMPA_NAMED_ABSORPTION_SPECTRUM_DEOXYHEMOGLOBIN,
    #         ]
    #     ),
    #     Tags.LINEAR_UNMIXING_COMPUTE_SO2: True,
    #     Tags.LINEAR_UNMIXING_NON_NEGATIVE: True,
    # }

    # sp.LinearUnmixing(settings, "linear_unmixing").run()

    _visualize_results(
        subject_id,
        wavelengths_nm,
        exp_id,
        melanin_volume_fraction=subject_data["melanin_fraction"],
        show_time_series=True,
        show_reconstruction=True,
    )
