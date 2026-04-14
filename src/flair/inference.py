# TODO
# test it rewritten to use S3 buckets insted of mounted volume
import os
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
OUT_BUCKET = "AT_results"
IN_BUCKET = "AT_Orthofotos"
IN_PREFIX_RASTER = "orthofotos"
OUT_PREFIX_RASTER = "AT/AT/2024/output/"

yamlfile_output_path = '/home/eouser/yamlfiles_inference'


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
    """Return files ending with ending with '.tif' in Directory."""
    return glob.glob(os.path.join(directory, "**", "*.tif"), recursive=True)

# === Function to update YAML configuration files ===
def update_yaml(input_filepath):
    def update_yaml_text(key, new_value, file_yaml_input, file_yaml_output):
        # Ensure string values are quoted
        if isinstance(new_value, str) and not (new_value.startswith('"') or new_value.startswith("'")):
            new_value = f'"{new_value}"'

        # Read template file and replace values
        lines_out = []
        with open(file_yaml_input, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{key}:"):
                    lines_out.append(f'{key}: {new_value}\n')
                else:
                    lines_out.append(line)
    

        # # Write updated file
        with open(file_yaml_output, "w", encoding="utf-8") as f:
            f.writelines(lines_out)

    # Paths for yaml and input/output tif
    yamlfile = '/home/eouser/FLAIR-1/configs/flair-1-config-detect.yaml'

    filename = input_filepath.split('/')
    filename = filename[-1]

    yamlfile = input_filepath + ".yaml"

    inputfile = input_filepath + '.tif'

    outputname = filename

    print("yaml out: " + yamlfile)
    update_yaml_text(key="output_name", new_value=outputname, 
                     file_yaml_input="proto.yaml", file_yaml_output=yamlfile)
    
    update_yaml_text(key="input_img_path", new_value=inputfile, file_yaml_input=yamlfile, 
                     file_yaml_output=yamlfile)



list_input = list_s3_files_in_folder_using_client(bucket_name=IN_BUCKET, prefix=IN_PREFIX_RASTER)


for input in list_input:
    input_filepath = input.replace(".tif","")

    yamlfile_name = input_filepath.split('/')
    yamlfile_name = yamlfile_name[-1]

    print(yamlfile_name)
    print(input_filepath)

    update_yaml(input_filepath)


    yamlfile_path = f'{yamlfile_output_path}{yamlfile_name}.yaml'
    
    # # # Leerzeichen ist wichtig
    osCommand = "/home/eouser/FLAIR-1/src/flair/flair_detect.sh " + yamlfile_path
    print(osCommand)

    if os.system(osCommand)!=0:
        print("error")
        exit(1)