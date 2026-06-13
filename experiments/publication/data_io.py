import h5py
import numpy as np


def load_hdf5(filepath, datasets, return_attrs=False):
    """
    Load specific datasets from an HDF5 file.
    """
    try:
        results = []
        with h5py.File(filepath, "r") as file:
            for dataset in datasets:
                if dataset in file:
                    data = file[dataset][()]
                    if return_attrs:
                        attrs = dict(file[dataset].attrs)
                        results.append((data, attrs))
                    else:
                        results.append(data)
                else:
                    raise KeyError(f"Dataset '{dataset}' not found in the file.")
        return results
    except Exception as e:
        raise KeyError(f"Failed to load datasets from file '{filepath}': {e}")


def add_hdf5_dataset(
    filepath: str,
    dataset_path: str,
    data: np.ndarray,
    attributes: dict = None,
):
    """
    add a dataset to an HDF5 file, creating groups if necessary
    """

    with h5py.File(filepath, "a") as f:
        if dataset_path in f:
            print(f"dataset_path '{dataset_path}' already exists. Overwriting.")
            del f[dataset_path]

        parent_group_path = "/".join(dataset_path.split("/")[:-1])
        dataset_name = dataset_path.split("/")[-1]

        step_group = f.require_group(parent_group_path)

        dataset = step_group.create_dataset(
            dataset_name,
            data=data,
            compression="gzip",
            compression_opts=4,
        )

        if attributes:
            for key, value in attributes.items():
                dataset.attrs[key] = (
                    value if type(value) in [str, int, float] else str(value)
                )


def delete_hdf5_dataset_or_group(filepath: str, dataset_path: str):
    """
    Delete a dataset or group from an HDF5 file.
    """
    with h5py.File(filepath, "a") as f:
        if dataset_path in f:
            del f[dataset_path]
        else:
            print(f"'{dataset_path}' not found in file '{filepath}'.")


def hdf5_dataset_exists(filepath: str, dataset_path: str) -> bool:
    """
    Check if a dataset exists in an HDF5 file.
    """
    with h5py.File(filepath, "r") as f:
        return dataset_path in f


def postprocess_sim_properties(data):
    # postprocess simulation properties
    data = [np.rot90(d, 1)[:-11, 7:-8] for d in data]
    data = np.stack(data, axis=0)
    return data
