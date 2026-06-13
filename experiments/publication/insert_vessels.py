from data_io import load_hdf5, add_hdf5_dataset
import matplotlib.pyplot as plt
from skimage.transform import resize

import numpy as np
from skimage.draw import disk
import random
import os
from scipy.ndimage import binary_dilation

import nrrd


def insert_vessels_into_mask(
    seg_mask: np.ndarray,
    vessel_diameter: int,
    vessel_class: int,
    target_class: int,
    num_vessels: int = 5,
    max_attempts_per_vessel: int = 100,
    cage: tuple = None,
    margin: int = 0,
    seed: int = 471,
) -> np.ndarray:
    """
    Insert circular vessel regions into a given class in a 2D segmentation mask,
    optionally within a defined cage and at a safe margin from neighboring classes.

    Parameters:
    seg_mask: 2D segmentation mask.
    vessel_diameter: Diameter of the circular vessel.
    vessel_class: Label for the inserted vessels.
    target_class: Class in which to place vessels (e.g., muscle).
    num_vessels: Number of vessels to insert.
    max_attempts_per_vessel: Max tries to place a single vessel.
    cage: Optional bounding box (min_row, min_col, max_row, max_col).
    margin: Distance (in pixels) the vessel must keep from other classes.
    seed: Optional random seed for reproducibility.

    """

    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    radius = vessel_diameter // 2
    output_mask = seg_mask.copy()

    # Create a mask of all non-target pixels
    non_target_mask = seg_mask != target_class

    # Expand forbidden zone by margin using binary dilation
    if margin > 0:
        struct_elem = np.ones((margin * 2 + 1, margin * 2 + 1), dtype=bool)
        forbidden_zone = binary_dilation(non_target_mask, structure=struct_elem)
    else:
        forbidden_zone = non_target_mask

    # Find candidate pixels within target class and outside forbidden zone
    candidate_mask = (seg_mask == target_class) & (~forbidden_zone)
    target_coords = np.argwhere(candidate_mask)

    if cage is not None:
        min_row, min_col, max_row, max_col = cage
        target_coords = [
            (r, c)
            for r, c in target_coords
            if min_row + radius <= r <= max_row - radius
            and min_col + radius <= c <= max_col - radius
        ]

    if not target_coords:
        print(
            f"No valid pixels in target class {target_class} with margin {margin} within cage."
        )
        return None

    placed = 0
    attempts = 0

    while placed < num_vessels and attempts < max_attempts_per_vessel * num_vessels:
        attempts += 1
        cy, cx = random.choice(target_coords)

        rr, cc = disk((cy, cx), radius, shape=seg_mask.shape)

        # Check that all pixels in the disk are target class and not in forbidden zone
        if np.all((seg_mask[rr, cc] == target_class) & (~forbidden_zone[rr, cc])):
            output_mask[rr, cc] = vessel_class
            placed += 1

    if placed < num_vessels:
        print(
            f"Warning: Only placed {placed}/{num_vessels} vessels after {attempts} attempts."
        )
        return None

    return output_mask


def main():

    from config import SIMDatasetConfig

    hybrid_mask_id = 1
    outpath = os.path.join(
        SIMDatasetConfig.segmentation_map_path, f"hybrid/{hybrid_mask_id}"
    )

    os.makedirs(outpath, exist_ok=True)

    cage = (100, 50, 250, 350)  # (min_row, min_col, max_row, max_col)

    SEED = 42
    MARGIN = 2  # Minimum distance from other classes

    MASK_SRC = "HDF5"  # "GT" (NRRD) or HDF5 (POSTPROCESSING/MASK)

    gt_nrrd_path = ""

    if MASK_SRC == "HDF5":

        basepath = SIMDatasetConfig.segmentation_map_path
        files = [
            f
            for f in os.listdir(basepath)
            if os.path.isfile(os.path.join(basepath, f)) and f.endswith(".hdf5")
        ]
    elif MASK_SRC == "GT":
        files = [
            f
            for f in os.listdir(gt_nrrd_path)
            if os.path.isfile(os.path.join(gt_nrrd_path, f)) and f.endswith(".nrrd")
        ]

    print(f"Found {len(files)} test files in {basepath}")

    counter = 0

    for file in files:

        print(f"Processing {file}")

        seg_mask_file = os.path.join(basepath, file)

        if MASK_SRC == "HDF5":
            seg_mask = load_hdf5(seg_mask_file, SIMDatasetConfig.hdf5_dataset)[0][0]
            seg_mask = np.rot90(seg_mask, 2)
        elif MASK_SRC == "GT":
            from nrrd import read

            seg_mask, _ = read(seg_mask_file)
            seg_mask = np.array(seg_mask).squeeze()
            seg_mask = np.flipud(seg_mask)
            # resize to 400x400
            seg_mask = resize(
                seg_mask, (400, 400), order=0, preserve_range=True, anti_aliasing=False
            )

        seg_mask_with_vessels = insert_vessels_into_mask(
            seg_mask,
            vessel_diameter=15,
            vessel_class=13,
            target_class=3,
            num_vessels=1,
            max_attempts_per_vessel=200,
            cage=cage,
            margin=MARGIN,
            seed=SEED,
        )
        if seg_mask_with_vessels is None:
            print(f"Failed to insert muscle vessels in {file}. Skipping.")
            continue

        seg_mask_with_vessels = insert_vessels_into_mask(
            seg_mask_with_vessels,
            vessel_diameter=25,
            vessel_class=14,
            target_class=8,
            num_vessels=1,
            max_attempts_per_vessel=200,
            cage=cage,
            margin=MARGIN,
            seed=SEED,
        )
        if seg_mask_with_vessels is None:
            print(f"Failed to insert SAT vessels in {file}. Skipping.")
            continue

        seg_mask_with_vessels = seg_mask

        plt.imshow(seg_mask_with_vessels, cmap="viridis")
        plt.colorbar()
        plt.title(f"{file}")
        # add vessel params as text
        plt.text(
            0.05,
            0.95,
            f"Muscle-Vessel: class 13,  d=20px, target class 3\nSAT-Vessel: class 14, d=30px, target class 8",
            transform=plt.gca().transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(facecolor="white", alpha=0.5, edgecolor="black"),
        )
        plt.savefig(os.path.join(outpath, file.split(".")[0] + ".png"))
        plt.close()

        # add trailing dimension for viewer
        seg_mask_with_vessels = seg_mask_with_vessels[:, :, np.newaxis]
        # save to nrrd
        nrrd_outpath = os.path.join(outpath, file)
        nrrd.write(nrrd_outpath, seg_mask_with_vessels)

        counter += 1

    print(f"Inserted vessels into {counter} masks and saved to {outpath}")


if __name__ == "__main__":
    main()
