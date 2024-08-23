#!/usr/bin/env python3

import argparse
import os
import sys
import logging
import pandas as pd

logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

def parse_args(args=None):
    description= 'Checks to ensure the file has content. Removes the file from the samplesheet if there is no data.'
    epilog = 'Example usage: python3 file_size_check.py <SAMPLE_SHEET>'
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument('samplesheet',
        help='Samplesheet to check.')
    return parser.parse_args(args)

def get_file_path(samplesheet):

    logging.debug("Setting up dataframe to extract path of files.")
    df = pd.read_csv(samplesheet)

    column_name = df.columns[1]
    file_path = df[column_name].iloc[1]
    path_only = os.path.dirname(file_path)

    logging.debug("Setting path up")
    path_only = path_only + "/"

    return path_only

def check_file_bytes(file_path):

    logging.debug("Setting up empty list and dictionary.")
    file_size_dict = {}
    files_to_check = []

    for filename in os.listdir(file_path):
        logging.debug(f"Processing {filename}.")
        path = file_path + filename
        size = os.path.getsize(path)
        file_size_dict[filename] = size

    for k,v in file_size_dict.items():
        if int(v) < 20:
            files_to_check.append(k)

    return files_to_check

def remove_from_samplesheet(list_files, samplesheet):

    outfile = "final_" + os.path.basename(samplesheet)

    with open(samplesheet, "r") as file, open(outfile, "w") as out:
        for line in file:
            if any(file in line for file in list_files):
                pass
            else:
                out.write(line)

    return out

def main(args=None):
    args = parse_args(args)
    file_path = get_file_path(args.samplesheet)
    files_to_check_bytes = check_file_bytes(file_path)
    remove_from_samplesheet(files_to_check_bytes, args.samplesheet)

if __name__ == "__main__":
    sys.exit(main())