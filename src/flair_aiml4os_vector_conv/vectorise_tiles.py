import os
import glob
from pathlib import Path

# Wenn Permission denied Fehlermeldung im Terminal
#chmod +x flair_vectorise.sh

# Pfad zum Hauptverzeichnis
dir_input = "/mnt/eo/projekt/2023_Essnet/results/Raster_tiled/"
dir_output = '/mnt/eo/projekt/2023_Essnet/results/Vektor/'
outputpathfile = f'/home/nnors/Vektor/'{filename}'.gpkg'

def update_yaml(filename):
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

    yamlfile = '/mnt/eo/projekt/2023_Essnet/results/yamlfiles/' + filename + '.yaml'
   
    # Paths for yaml and input/output tif
    
    yamlfile
   
    filename = filename.split('/')
    filename = filename[-1]
    
   

    inputfile = filename + '.tif'

    outputname = f'{outputpathfile}/{filename}.gpkg'

    p = Path(__file__).with_name('config-vector_proto.yaml')
    file_yaml_input = p.absolute()

   
    update_yaml_text(key = "input_file", new_value = inputfile, 
                     file_yaml_input = file_yaml_input, file_yaml_output = yamlfile)
    
    update_yaml_text(key = "output_file", new_value=outputname, file_yaml_input=file_yaml_input, 
                     file_yaml_output= yamlfile)


def list_tif_files(directory):
    return glob.glob(os.path.join(dir_input, "**", "*.tif"), recursive=True)


list_input = list_tif_files(dir_input)


for input in list_input:
    
    input_filepath = input.replace(".tif","")

    yamlfile_name = input_filepath.split('/')
    yamlfile_name = yamlfile_name[-1]


    yamlfile = '/home/nnors/Documents/Essnet/FLAIR_1_fork/FLAIR-1/configs_vector/' + yamlfile_name + '.yaml'
    print(yamlfile_name)

    update_yaml(input_filepath)
    
    # Leerzeichen ist wichtig
    
    #osCommand="/home/nnors/Documents/Essnet/FLAIR_1_fork/FLAIR-1/src/flair_aiml4os_vector_conv/flair_vectorise.sh " + yamlfile
    #print(osCommand)

   # if os.system(osCommand)!=0:
   #     print("error")
   #     exit(1)