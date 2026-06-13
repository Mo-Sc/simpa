import os
import pandas as pd
from tqdm import tqdm
from data_io import load_hdf5
from segmentation_utils import (
    split_skin_into_epidermis_and_dermis,
    create_seg_volume_pv,
)
from pipelines import run_optical_simulation


def skin_melanin_pa_intensity_from_xslx(
    xlsx_path: str,
    sheet_name: str = "700",
    subject_id: str = "002-017-048-000",
    feature: str = "original_firstorder_Mean",
):
    """
    load the extracted intensity values from the xlsx file
    """
    # Load the xlsx file
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)

    # Filter the DataFrame for the specified subject
    subject_df = df[df["subject_id"] == subject_id]

    # Convert to a list and return
    return subject_df[feature].tolist()[0]


def pa_intensity_to_melanosome_fraction(
    pa_intensity,
    min_intensity=300,
    max_intensity=3500,
    min_fraction=0.01,
    max_fraction=0.43,
):
    """Map photoacoustic signal at 700nm to estimated melanosome volume fraction.
    Based on:
    [Jacques 1996]:
    for light skinned caucasions, fv = 1-3%
    for well-tanned caucasions and Mediterraneans, fv = 11-16%
    for darkly pigmented Africans, fv = 18-43%.

    """
    # Clamp intensity to min/max range
    # pa_intensity = max(min(pa_intensity, max_intensity), min_intensity)

    # Normalize intensity to [0, 1]
    norm = (pa_intensity - min_intensity) / (max_intensity - min_intensity)

    # Scale to [0.01, 0.43] for melanosome volume fraction (Jacques range)
    fv = min_fraction + norm * (max_fraction - min_fraction)

    return fv


def main():

    from config import FSTDatasetConfig, PADDatasetConfig

    EXP_ID = 30

    DatasetConfig = FSTDatasetConfig
    # DatasetConfig = PADDatasetConfig

    outpath = os.path.join(DatasetConfig.output_path, f"{EXP_ID}")
    os.environ["SIMPA_SAVE_DIRECTORY"] = outpath
    os.makedirs(outpath, exist_ok=True)

    subjects_data = dict()

    segmask_files = [
        f
        for f in os.listdir(DatasetConfig.segmentation_map_path)
        if os.path.isfile(os.path.join(DatasetConfig.segmentation_map_path, f))
        and f.endswith(".hdf5")
    ]

    print(
        f"Found {len(segmask_files)} segmentation map files in {DatasetConfig.segmentation_map_path}"
    )

    for segfile in tqdm(segmask_files):

        outfilepath = os.path.join(outpath, segfile)
        segfilepath = os.path.join(DatasetConfig.segmentation_map_path, segfile)

        if os.path.exists(outfilepath):
            print(f"Skipping {segfile} as it already exists")
            continue

        tqdm.write(f"Processing from {segfilepath}")

        subject_id = segfile.split(".")[0]

        if subject_id not in subjects_data:
            subjects_data[subject_id] = dict()

        # load skin melanin signal
        mel_signal = skin_melanin_pa_intensity_from_xslx(
            DatasetConfig.skin_intensity_xlsx_path,
            sheet_name="700_980",
            subject_id=subject_id,
        )

        melanin_fraction = pa_intensity_to_melanosome_fraction(
            mel_signal,
            DatasetConfig.melanin_min_intensity,
            DatasetConfig.melanin_max_intensity,
            DatasetConfig.melanin_min_fraction,
            DatasetConfig.melanin_max_fraction,
        )

        tqdm.write(
            f"Melanin signal: {mel_signal}, estimated melanin fraction: {melanin_fraction}"
        )

        subjects_data[subject_id]["mel_signal"] = mel_signal
        subjects_data[subject_id]["melanin_fraction"] = melanin_fraction

        seg_mask = load_hdf5(segfilepath, DatasetConfig.hdf5_dataset)[0][0]
        seg_mask = split_skin_into_epidermis_and_dermis(
            seg_mask,
            DatasetConfig.skin_id,
            DatasetConfig.epidermis_id,
            DatasetConfig.dermis_id,
            DatasetConfig.epidermis_px,
        )

        # turn into volume, add space for transducer
        seg_volume = create_seg_volume_pv(seg_mask, pv=DatasetConfig.pv_effect)

        tqdm.write(f"Segmentation volume shape: {seg_volume.shape}")

        subjects_data[subject_id]["seg_volume"] = seg_volume
        subjects_data[subject_id]["segmentation_shape"] = seg_volume.shape

        # run simulation
        run_optical_simulation(
            exp_id=EXP_ID,
            subject_id=subject_id,
            subject_data=subjects_data[subject_id],
            wavelengths_nm=DatasetConfig.wavelengths,
            pv_effects=DatasetConfig.pv_effect,
        )

        tqdm.write(f"Finished processing {segfile}")

    print("All files processed.")

    # try:
    #     notify(
    #         f"AIMI-05 finished sim exp id {EXP_ID} on {len(segmask_files)} files",
    #     )
    # except Exception as e:
    #     print(f"Failed to send notification: {e}")


if __name__ == "__main__":
    main()
