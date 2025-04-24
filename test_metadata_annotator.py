"""Test script to test metadata-annotator standalone
"""
#import argparse
#import xarray as xr
from metadata_annotator.annotate import annotate_granule
input_file =   '/Users/smurthy1/NCRs/DAS-2335/SPL3FTP/SC_SPL3FTP_subsetted_2_variables.nc4'  
output_file_path = '/Users/smurthy1/NCRs/DAS-2335/SPL3FTP/SC_SPL3FTP_subsetted_annotated_2_variables.nc4'
short_name = 'SPL3FTP'
config_file = '/Users/smurthy1/NCRs/DAS-2335/harmony-metadata-annotator/metadata_annotator/earthdata_varinfo_config.json'


annotate_granule(
        input_file, output_file_path, config_file, 'SPL3FTP'
        )


# def main(input_file, output_file_path, short_name, 
#          config_file="/Users/smurthy1/NCRs/DAS-2335/harmony-metadata-annotator/metadata_annotator/earthdata_varinfo_config.json"):
#     """
#     This is the main function of the script.

#     Args:
#         input_file: 
#         output_file_path: 
#         short_name: 
#         config_file: 
#     """
#     print(f"input_file: {input_file}")
#     print(f"output_file_path: {output_file_path}")
#     print(f"short_name: {short_name}")
#     if config_file:
#         print(f"config_file: {config_file}")
    
#     annotate_granule(
#         input_file, output_file_path, config_file, 'SPL3SMP_E'
#     )    

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Test metadata annotator for different collections")
#     parser.add_argument("input_file", help="input file")
#     parser.add_argument("output_file_path", help="output file path")
#     parser.add_argument("short_name", help="short name of collection")
#     parser.add_argument("--config_file", help="config file")

#     args = vars(parser.parse_args())
#     #args = parser.parse_args()

#     main(args.input_file, args.output_file_path, 
#          args.short_name, args.optional_arg)
