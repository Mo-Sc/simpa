import numpy as np
import torch
from scipy.ndimage import gaussian_filter
from config import segmentation_class_mapping


def split_skin_into_epidermis_and_dermis(
    segmentation_mask: np.ndarray,
    skin_class_id: int,
    epidermis_class_id: int,
    dermis_class_id: int,
    epidermis_thickness: int,
    rot90: int = 2,
):
    """
    Splits the skin class in a segmentation mask into epidermis and dermis.

    segmentation_mask: 2D numpy array (e.g., shape [400, 400]) with original class labels
    skin_class_id: the integer label used for the 'skin' class in the original mask
    epidermis_class_id: new label for the epidermis
    dermis_class_id: new label for the dermis
    epidermis_thickness: number of pixels to assign to epidermis from the top of skin regions

    """
    updated_mask = np.rot90(segmentation_mask.copy(), rot90)
    height, width = updated_mask.shape

    for x in range(width):
        column = updated_mask[:, x]
        skin_indices = np.where(column == skin_class_id)[0]

        if len(skin_indices) == 0:
            continue  # No skin in this column

        # From the top skin pixel, label epidermis_thickness as epidermis
        start_idx = skin_indices[0]
        end_idx = start_idx + epidermis_thickness

        # Ensure we dont go beyond actual skin pixels
        actual_epidermis_indices = skin_indices[skin_indices < end_idx]
        actual_dermis_indices = skin_indices[skin_indices >= end_idx]

        updated_mask[actual_epidermis_indices, x] = epidermis_class_id
        updated_mask[actual_dermis_indices, x] = dermis_class_id

    return updated_mask


def create_seg_volume_pv(seg_mask, pv=False, pv_sigma=1.5, seg_class_mapping=None):
    """
    Takes a 2D segmentation mask and creates a 3D volume by adding a y dimension and tiling.
    Also pads the top with zeros to make space for the transducer.
    If pv is True, creates a pixel-wise volume where each voxel contains a distribution over classes (one-hot smoothed with gaussian filter).
    This simulates partial volume effects

    """

    if seg_class_mapping is None:
        seg_class_mapping = segmentation_class_mapping

    # rotate segmentation mask
    seg_mask = np.rot90(seg_mask, 1)

    # pad 315 columns to the top (to make space for the transducer, shifts the actual segmentation into the fov)
    seg_mask = np.pad(
        seg_mask,
        ((0, 0), (315, 0)),
        "constant",
        constant_values=0,
    )

    # add a y dimension
    seg_volume = np.expand_dims(seg_mask, axis=1)
    seg_volume = np.tile(seg_volume, (1, 150, 1))

    if pv:

        # indices are class labels. Works for non-consecutive class labels
        C = max(seg_class_mapping().keys()) + 1
        seg_volume_pv = torch.zeros((C, *seg_volume.shape), dtype=torch.float32)

        # Fill based on actual class labels (not on their order in all_class_labels)
        for class_label in seg_class_mapping().keys():
            mask = seg_volume == class_label
            if mask.any():
                seg_volume_pv[class_label][mask] = 1.0

        seg_volume_pv = gaussian_filter(
            seg_volume_pv, sigma=(0, pv_sigma, pv_sigma, pv_sigma)
        )  # smooth spatial dims only

        # normalize the segmentation volume
        # each voxel contains a distribution over classes with sum 1
        seg_volume_pv /= seg_volume_pv.sum(axis=0, keepdims=True)

    return seg_volume if not pv else seg_volume_pv
