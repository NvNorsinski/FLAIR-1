#!/usr/bin/env bash
set -euo pipefail

# Reproject all GeoTIFFs in a folder to EPSG:31255 using gdalwarp.
# - Skips files already in EPSG:31255 (copies with compression options).
# - Writes outputs to  (or custom OUTPUT_DIR).
# - Applies LZW compression and tiling to output GeoTIFFs.
#
# Usage:
#  ./images_reproject.sh s3://input-bucket/input-prefix/ s3://output-bucket/output-prefix/
#
# Requirements:
#   - AWS CLI installed and configured (for listing S3 files)
# pip install awscli
#   - GDAL installed and available in PATH (gdalwarp, gdalinfo, gdal_translate)
#   - /tmp has enough space for temporary files

INPUT_S3="${1:?Usage: $0 s3://input-bucket/input-prefix/ s3://output-bucket/output-prefix/}"
OUTPUT_S3="${2:?Usage: $0 s3://input-bucket/input-prefix/ s3://output-bucket/output-prefix/}"
TARGET_EPSG="EPSG:3857"

TMPDIR="${TMPDIR:-/tmp}"


mapfile -t files < <(aws s3 ls "$INPUT_S3" --recursive | awk '{print $4}' | grep -Ei '\.tif(f)?$' | sort)


if [[ ${#files[@]} -eq 0 ]]; then
  echo "No GeoTIFF files found in '$INPUT_S3'."
  exit 0
fi

echo "Found ${#files[@]} TIFF file(s) in '$INPUT_S3'. Output -> '$OUTPUT_S3'"
echo "Target CRS: $TARGET_EPSG"


# Function: extract EPSG code from gdalinfo output
# Handles patterns like:
#   AUTHORITY["EPSG","3857"]
#   EPSG:31255
extract_epsg() {
  local file="$1"
  local epsg=""
  # Try AUTHORITY form
  epsg="$(gdalinfo "$file" 2>/dev/null | grep -Eo 'AUTHORITY\["EPSG","[0-9]+"\]' | head -n1 | grep -Eo '[0-9]+' || true)"
  if [[ -z "$epsg" ]]; then
    # Try simple EPSG:NNNN form
    epsg="$(gdalinfo "$file" 2>/dev/null | grep -Eo 'EPSG:[0-9]+' | head -n1 | cut -d: -f2 || true)"
  fi
  echo "$epsg"
}


for s3_key in "${files[@]}"; do
  base="$(basename "$s3_key")"
  stem="${base%.*}"
  local_in="$TMPDIR/${stem}_in.tif"
  local_out="$TMPDIR/${stem}_EPSG3857.tif"
  s3_in_path="${INPUT_S3%/}/$s3_key"
  s3_out_path="${OUTPUT_S3%/}/${stem}_EPSG3857.tif"

  echo "----------------------------------------"
  echo "Processing: $s3_key"
 # Download from S3
  aws s3 cp "$s3_in_path" "$local_in"

  # Check current EPSG
  src_epsg="$(extract_epsg "$local_in")"
  if [[ -z "$src_epsg" ]]; then
    echo "  Warning: Could not detect EPSG in '$base'. Will proceed to warp to $TARGET_EPSG."
  else
    echo "  Detected EPSG:$src_epsg"
  fi

  if [[ "$src_epsg" == "3857" ]]; then
    echo "  Already in $TARGET_EPSG. Copying with compression options..."
    gdal_translate \
      -co COMPRESS=ZSTD -co TILED=YES -ot Int8 -co BIGTIFF=IF_SAFER \
      "$local_in" "$local_out"
    aws s3 cp "$local_out" "$s3_out_path"
    echo "  -> Uploaded: $s3_out_path"
    rm -f "$local_in" "$local_out"
    continue
  fi

  echo "  Warping to $TARGET_EPSG..."

  gdalwarp \
    -t_srs "$TARGET_EPSG" \
    -r near \
    -srcnodata nan -dstnodata -128 \
    -multi -wo NUM_THREADS=ALL_CPUS \
    -overwrite \
    -ot Int8 \
    -co COMPRESS=ZSTD -co TILED=YES -co BIGTIFF=IF_SAFER \
    "$local_in" "$local_out"

  aws s3 cp "$local_out" "$s3_out_path"
  echo "  -> Uploaded: $s3_out_path"
  rm -f "$local_in" "$local_out"
done

echo "----------------------------------------"
echo "Done. Outputs in: $OUTPUT_DIR"
``


