# Create mask on predictive outcome based on orthofotos. NaN Values in orthoimages are used to mask out Nodata areas in predictive outcome
import math
import os
from pathlib import Path

import numpy as np
import rasterio
from rasterio import Env
from rasterio.windows import Window


# out_directory = "/mnt/eo/projekt/2023_Essnet/results/masked/"
#out_directory = "/home/nnors/masked/"
out_directory = '/mnt/mount-point/AT/AT/2024/output_masked/'

#masks_directory = Path("/mnt/eo/projekt/2023_Essnet/results/Orthofotos/")
masks_directory = Path("/mnt/orthofotos/orthofotos/")
#masks_directory = Path("/home/nnors/Orthofotos/")

#target_directory = Path("/mnt/eo/projekt/2023_Essnet/results/Raster/")
target_directory = Path('/mnt/mount-point/AT/AT/2024/output/raster/')
#target_directory = Path("/home/nnors/Raster/")

substring = 'NIR' 


mask_candidates = [i for i in masks_directory.iterdir() if substring in i.name and i.suffix.lower() == ".tif"]
mask_files = [str(p) for p in mask_candidates]
#mask_files = [str(p) for p in masks_directory.iterdir() if p.suffix.lower() == ".tif"]
#mask_files = [p for p in masks_directory if '.tif' in p]
target_files = [str(p) for p in target_directory.iterdir() if p.suffix.lower() == ".tif"]

# Choose how to mark masked pixels in output:
# - If you want NaN (float rasters), keep output_dtype as float32 and nodata_value=None
# - If target is integer and can't hold NaN, set nodata_value to something valid (e.g., -9999)
use_nan_output = True
nodata_value = None  # e.g., -9999 for integer output

# number of bands of the mask providing image
number_of_bands = 1
bands_index = [i for i in range(1, number_of_bands + 1)]

STRIPE_ROWS = 8192  # process ~8k rows per stripe; increase if you have more RAM
GDAL_CACHE_MB = 2048
NUMBER_CORES = 4


def create_mask(mask_path, target_path, out_path):
    with Env(GDAL_NUM_THREADS=NUMBER_CORES, GDAL_CACHEMAX=GDAL_CACHE_MB):
        with rasterio.open(mask_path) as mask_ds, rasterio.open(target_path) as tgt_ds:
            # Sanity checks (size, georeferencing)
            if mask_ds.width != tgt_ds.width or mask_ds.height != tgt_ds.height or mask_ds.transform != tgt_ds.transform:
                raise ValueError("Mask and target must match in width/height, transform")

            # Expect x-band mask and 1-band target
            if mask_ds.count != number_of_bands:
               
                raise ValueError(f"Expected a x-band mask; got {mask_ds.count} bands.")
            if tgt_ds.count != 1:
                raise ValueError(f"Expected a single-band target; got {tgt_ds.count} bands.")

            # Output dtype / nodata handling
            promote_to_float = use_nan_output and not np.issubdtype(np.dtype(tgt_ds.dtypes[0]), np.floating)
            out_dtype = np.float32 if (use_nan_output or promote_to_float) else tgt_ds.dtypes[0]
            out_nodata = None if use_nan_output else nodata_value

            profile = tgt_ds.profile.copy()
            profile.update({
                "count": 1,
                "dtype": out_dtype,
                "nodata": out_nodata,
                "tiled": True,
                "compress": "zstd",
                "predictor": 3 if np.issubdtype(np.dtype(out_dtype), np.floating) else 2,
                "BIGTIFF": "YES",
                "NUM_THREADS": 4,
                "blockxsize": tgt_ds.profile.get("blockxsize", 512),
                "blockysize": tgt_ds.profile.get("blockysize", 512),
            })

            height, width = tgt_ds.height, tgt_ds.width
            stripes = math.ceil(height / STRIPE_ROWS)

            with rasterio.open(out_path, "w", **profile) as out_ds:
                for s in range(stripes):
                    print(str(s) + "/" + str(stripes))
                    row_off = s * STRIPE_ROWS
                    rows = min(STRIPE_ROWS, height - row_off)
                    win = Window(col_off=0, row_off=row_off, width=width, height=rows)

                    # Read 2-band mask for this stripe: shape (3, rows, cols)
                    # number of bands can be changed
                    mask_block = mask_ds.read(indexes=bands_index, window=win)

                    # Compute "all three bands == 0" per pixel (vectorized)
                    all_zero = (mask_block == 0).all(axis=0)  # boolean (rows, cols)

                    # Read single-band target stripe
                    tgt_block = tgt_ds.read(indexes=1, window=win)

                    # Cast once if output needs NaN but input is integer
                    if promote_to_float and tgt_block.dtype != np.float32:
                        tgt_block = tgt_block.astype(np.float32, copy=False)

                    # Apply mask in one vectorized operation
                    if use_nan_output:
                        tgt_block[all_zero] = np.nan
                    else:
                        if nodata_value is None:
                            raise ValueError("Please set 'nodata_value' when use_nan_output=False.")
                        tgt_block[all_zero] = nodata_value

                    # Write stripe
                    out_ds.write(tgt_block, 1, window=win)

    print(f"Done. Wrote masked raster to: {out_path}")


for mask, target in zip(mask_files, target_files):
    print(mask)
    print(target)
    out_filename = os.path.basename(target)
    out_path = f"{out_directory}/{out_filename}"
    create_mask(mask, target, out_path)




