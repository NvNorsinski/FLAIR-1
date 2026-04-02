
# TODO adapt to cloud and test
from osgeo import gdal, osr

import os
import tempfile
import glob
from pathlib import Path

import boto3



#-----------------------------------------------------------------------
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

#---------------------------------------------------------------------

BUCKET = "AT_results"
BUCKET_PREFIX = "AT/AT/2024/output/output_reprojected/"
OUT_PREFIX = "AT/AT/2024/split_tifs/"



def list_s3_files_in_folder_using_client(bucket_name, prefix):
    """Return files ending with ending with '.tif' in S3 Bucket."""
    paginator = s3.get_paginator("list_objects_v2")
    files = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".tif"):
                files.append(obj["Key"])
    return files


def list_tif_files(directory):
    """List full paths of all files in the given directory ending with '.tif'."""
    return [os.path.join(directory, f) for f in os.listdir(directory) if f.lower().endswith('.tif')]

#list_files = list_tif_files('/mnt/eo/projekt/2023_Essnet/results/Raster_reproject_3/')

list_files = list_s3_files_in_folder_using_client(bucket_name=BUCKET, prefix=BUCKET_PREFIX)

#output_dir = '/mnt/eo/projekt/2023_Essnet/results/Raster_tiled'


nr_subdivisions = 20


def get_extent(dataset):
    cols = dataset.RasterXSize
    rows = dataset.RasterYSize
    transform = dataset.GetGeoTransform()
    minx = transform[0]
    maxx = transform[0] + cols * transform[1] + rows * transform[2]

    miny = transform[3] + cols * transform[4] + rows * transform[5]
    maxy = transform[3]

    return {
            "minX": str(minx), "maxX": str(maxx),
            "minY": str(miny), "maxY": str(maxy),
            "cols": str(cols), "rows": str(rows)
            }

def create_tiles(minx, miny, maxx, maxy, n):
    width = maxx - minx
    height = maxy - miny

    matrix = []

    for j in range(n, 0, -1):
        for i in range(0, n):

            ulx = minx + (width/n) * i # 10/5 * 1
            uly = miny + (height/n) * j # 10/5 * 1

            lrx = minx + (width/n) * (i + 1)
            lry = miny + (height/n) * (j - 1)
            matrix.append([[ulx, uly], [lrx, lry]])

    return matrix

def upload_file_to_s3(local_path, bucket, key):
    s3.upload_file(local_path, bucket, key)
    print(f"Uploaded {local_path} to s3://{bucket}/{key}")


def split_s3_geotiff(s3_key, n, bucket, out_prefix):
    # Download file to temp
    raw_file_name = os.path.splitext(os.path.basename(s3_key))[0].replace("_downsample", "")
    with tempfile.TemporaryDirectory() as tmpdir:
        local_in = os.path.join(tmpdir, os.path.basename(s3_key))
        s3.download_file(bucket, s3_key, local_in)
        dataset = gdal.Open(local_in)
        band = dataset.GetRasterBand(1)
        transform = dataset.GetGeoTransform()
        extent = get_extent(dataset)

        minx = float(extent["minX"])
        maxx = float(extent["maxX"])
        miny = float(extent["minY"])
        maxy = float(extent["maxY"])


        tiles = create_tiles(minx, miny, maxx, maxy, n)
        xOrigin = transform[0]
        yOrigin = transform[3]
        pixelWidth = transform[1]
        pixelHeight = -transform[5]

        tile_num = 0
        for tile in tiles:
            minx_tile = tile[0][0]
            maxx_tile = tile[1][0]
            miny_tile = tile[1][1]
            maxy_tile = tile[0][1]
            p1 = (minx_tile, maxy_tile)
            p2 = (maxx_tile, miny_tile)
            i1 = int((p1[0] - xOrigin) / pixelWidth)
            j1 = int((yOrigin - p1[1])  / pixelHeight)
            i2 = int((p2[0] - xOrigin) / pixelWidth)
            j2 = int((yOrigin - p2[1]) / pixelHeight)
            new_cols = i2-i1
            new_rows = j2-j1
            data = band.ReadAsArray(i1, j1, new_cols, new_rows)
            new_x = xOrigin + i1*pixelWidth
            new_y = yOrigin - j1*pixelHeight
            new_transform = (new_x, transform[1], transform[2], new_y, transform[4], transform[5])
            output_file_base = f"{raw_file_name}_{tile_num}.tif"
            local_out = os.path.join(tmpdir, output_file_base)
            driver = gdal.GetDriverByName('GTiff')
            dst_ds = driver.Create(local_out, new_cols, new_rows, 1, gdal.GDT_Int16,
                                   options=["COMPRESS=ZSTD", "TILED=YES"])
            dst_ds.GetRasterBand(1).WriteArray(data)
            tif_metadata = {
                "minX": str(minx_tile), "maxX": str(maxx_tile),
                "minY": str(miny_tile), "maxY": str(maxy_tile)
            }
            dst_ds.SetMetadata(tif_metadata)
            dst_ds.SetGeoTransform(new_transform)
            wkt = dataset.GetProjection()
            srs = osr.SpatialReference()
            srs.ImportFromWkt(wkt)
            dst_ds.SetProjection(srs.ExportToWkt())
            dst_ds = None
            # Upload to S3
            s3_out_key = f"{out_prefix.rstrip('/')}/{raw_file_name}/{output_file_base}"
            upload_file_to_s3(local_out, bucket, s3_out_key)
            tile_num += 1
        dataset = None


for s3_key in list_files:
    split_s3_geotiff(s3_key, nr_subdivisions, BUCKET, OUT_PREFIX)
