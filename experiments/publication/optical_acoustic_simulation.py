import os
from simpa import Tags
import numpy as np
from tqdm import tqdm

from data_io import load_hdf5
from segmentation_utils import (
    split_skin_into_epidermis_and_dermis,
    create_seg_volume_pv,
)
from pipelines import run_optical_acoustic_simulation


def main():

    from config import SIMDatasetConfig as DatasetConfig

    EXP_ID = 0

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

        # load and prepare the segmentation volume
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

        random_mel_fraction = np.random.uniform(
            DatasetConfig.random_mel_range[0], DatasetConfig.random_mel_range[1]
        )

        subjects_data[subject_id]["melanin_fraction"] = random_mel_fraction

        run_optical_acoustic_simulation(
            exp_id=EXP_ID,
            subject_id=subject_id,
            subject_data=subjects_data[subject_id],
            wavelengths_nm=DatasetConfig.wavelengths,
            pv_effects=DatasetConfig.pv_effect,
        )


if __name__ == "__main__":
    main()
