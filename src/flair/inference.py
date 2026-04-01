# TODO
# yaml file updates, input , output paths
import os
import glob
from pathlib import Path

# Pfad zum Hauptverzeichnis
dir_input = "/mnt/eo/projekt/2023_Essnet/results/Raster_tiled/"
outputpath = '/home/nnors/Vektor/'
yamlfile_output_path = '/mnt/eo/projekt/2023_Essnet/results/yamlfiles/'

def update_yaml(input_filepath):
    def update_yaml_text(key, new_value, file_yaml_input, file_yaml_output):
        # Ensure string values are quoted
        if isinstance(new_value, str) and not (new_value.startswith('"') or new_value.startswith("'")):
            new_value = f'"{new_value}"'

        #Read template file and replace values
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

    # output yamlfile
    filename = input_filepath.split('/')
    filename = filename[-1]

    yamlfile = f'{yamlfile_output_path}{filename}.yaml'


    
    inputfile_raster = f'{dir_input}{filename}.tif'

    outputname_geopackage = f'{outputpath}/{filename}.gpkg'

    p = Path(__file__).with_name('config-vector_proto.yaml')
    #file_yaml_input = p.absolute()
    file_yaml_input = '/home/eouser/FLAIR-1/configs/flair-1-config-detect.yaml'

   
    update_yaml_text(key = "input_file", new_value = f'{input_filepath}.tif', 
                     file_yaml_input = file_yaml_input, file_yaml_output = yamlfile)
    
    update_yaml_text(key = "output_file", new_value=outputname_geopackage, file_yaml_input=yamlfile, 
                     file_yaml_output=yamlfile)


def list_tif_files(directory):
    return glob.glob(os.path.join(dir_input, "**", "*.tif"), recursive=True)


list_input = list_tif_files(dir_input)


for input in list_input:
    input_filepath = input.replace(".tif","")

    yamlfile_name = input_filepath.split('/')
    yamlfile_name = yamlfile_name[-1]


   
    print(yamlfile_name)
    print(input_filepath)


    update_yaml(input_filepath)


    yamlfile_path = f'{yamlfile_output_path}{yamlfile_name}.yaml'
    
    # # # Leerzeichen ist wichtig
    osCommand="/home/eouser/FLAIR-1/src/flair/flair_detect.sh " + yamlfile_path
    print(osCommand)

    if os.system(osCommand)!=0:
        print("error")
        exit(1)