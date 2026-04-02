#!/bin/bash

# Usage: ./merge_geopackages.sh <input_dir> <output_file>
INPUT_DIR="${1:-.}"
OUTPUT_FILE="${2:-merged.gpkg}"
LAYER_NAME="merged"

# Find all .gpkg files in subdirectories
mapfile -t gpkg_files < <(find "$INPUT_DIR" -type f -name "*.gpkg")

if [[ ${#gpkg_files[@]} -eq 0 ]]; then
    echo "No GPKG files found in $INPUT_DIR"
    exit 1
fi

# Merge using ogr2ogr
# First file: create output, others: append
for i in "${!gpkg_files[@]}"; do
  echo $i 
    if [[ $i -eq 0 ]]; then
        ogr2ogr -f GPKG -nln "$LAYER_NAME" "$OUTPUT_FILE" "${gpkg_files[$i]}"
    else
        ogr2ogr -f GPKG -nln "$LAYER_NAME" -append "$OUTPUT_FILE" "${gpkg_files[$i]}"
    fi
done

echo "Merged ${#gpkg_files[@]} files into $OUTPUT_FILE (layer: $LAYER_NAME)"