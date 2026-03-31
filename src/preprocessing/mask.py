import boto3
from pathlib import Path

import numpy as np

import math
import os
import tempfile
import re

with open('/home/eouser/ec2credentials') as f:
    content = f.read()
list_content = content.split(sep = ':')

access_key = list_content[0]
secret_key = list_content[1]


endpoint_url = "s3.waw3-2.cloudferro.com"
endpoint_url_https = "https://s3.waw3-2.cloudferro.com"
region_name = "US"

try:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        endpoint_url=endpoint_url_https,
        region_name=region_name,
    )

    print(s3.list_buckets()["Buckets"])

except Exception as issue:
    print("The following error occurred:")
    print(issue)


os.environ["AWS_ACCESS_KEY_ID"] = access_key
os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
os.environ["AWS_REGION"] = region_name
os.environ["AWS_S3_ENDPOINT"] = endpoint_url
os.environ["GDAL_S3_ENDPOINT"] = endpoint_url
os.environ["AWS_S3_USE_HTTPS"] = "YES"
os.environ["AWS_S3_ADDRESSING_STYLE"] = "path" 
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["CPL_VSIL_USE_TEMP_FILE_FOR_RANDOM_WRITE"] = "YES"


import rasterio
from rasterio import Env
from rasterio.windows import Window

MASKS_BUCKET = "AT_Orthofotos"
MASKS_PREFIX = "orthofotos/"
TARGET_BUCKET = "AT_results"
TARGET_PREFIX = "AT/AT/2024/output/raster/"
OUT_BUCKET = "AT_results"
OUT_PREFIX = "AT/AT/2024/output_masked/"


def s3_out_path(target_s3_uri):
    # Extract filename and build output S3 URI
    filename = Path(target_s3_uri).name
    return f"s3://{OUT_BUCKET}/{OUT_PREFIX}{filename}"

def list_s3_tifs(bucket, prefix, substring=None):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(".tif") and (substring is None or substring in key):
                yield f"s3://{bucket}/{key}"


def s3_object_exists(s3_uri):
    """
    Check if an S3 object exists.
    s3_uri: str, e.g. 's3://bucket/key'
    Returns True if exists, False otherwise.
    """
    s3_uri_match = re.match(r"s3://([^/]+)/(.+)", s3_uri)
    if not s3_uri_match:
        return False
    bucket, key = s3_uri_match.groups()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        else:
            raise

mask_files = list(list_s3_tifs(MASKS_BUCKET, MASKS_PREFIX, substring = 'NIR'))

# Edit substring if necessary
target_files = list(list_s3_tifs(TARGET_BUCKET, TARGET_PREFIX, substring='_lc'))


use_nan_output = True
nodata_value = None  # e.g., -9999 for integer output

# number of bands of the mask providing image
number_of_bands = 1
bands_index = [i for i in range(1, number_of_bands + 1)]

STRIPE_ROWS = 2048  
GDAL_CACHE_MB = 2048
NUMBER_CORES = 4


def create_mask(mask_path, target_path, out_path):
    tempfile.NamedTemporaryFile()
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmpfile:
        local_out = tmpfile.name

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

            with rasterio.open(local_out, "w", **profile) as out_ds:
                for s in range(stripes):
                    print(str(s) + "/" + str(stripes))
                    row_off = s * STRIPE_ROWS
                    rows = min(STRIPE_ROWS, height - row_off)
                    win = Window(col_off=0, row_off=row_off, width=width, height=rows)

                    # Read 2-band mask for this stripe: shape (3 or 1, rows, cols)
                    # number of bands can be changed
                    mask_block = mask_ds.read(indexes=bands_index, window=win)

                    # Compute "all bands == 0" per pixel (vectorized)
                    all_zero = (mask_block == 0).all(axis=0)  # boolean (rows, cols)

                    # Read single-band target stripe
                    tgt_block = tgt_ds.read(indexes=1, window=win)

                    # Cast once if output needs NaN but input is integer
                    if promote_to_float and tgt_block.dtype != np.float32:
                        tgt_block = tgt_block.astype(np.float32, copy=False)

                    
                    if use_nan_output:
                        tgt_block[all_zero] = np.nan
                    else:
                        if nodata_value is None:
                            raise ValueError("Please set 'nodata_value' when use_nan_output=False.")
                        tgt_block[all_zero] = nodata_value

                    # Write stripe
                    out_ds.write(tgt_block, 1, window=win)

        s3_uri_match = re.match(r"s3://([^/]+)/(.+)", out_path)
        if s3_uri_match:
            bucket, key = s3_uri_match.groups()
            s3.upload_file(local_out, bucket, key)
            print(f"Uploaded {local_out} to {out_path}")
        else:
            print("Invalid S3 URI:", out_path)

    os.remove(local_out)

    print(f"Done. Wrote masked raster to: {out_path}")


for mask, target in zip(mask_files, target_files):
    print(mask)
    print(target)
    out_path = s3_out_path(target)
    print(out_path)
    if s3_object_exists(out_path):
        print(f"{out_path} already exists, skipping.")
        continue
    create_mask(mask, target, out_path)