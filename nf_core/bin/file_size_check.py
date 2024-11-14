#!/usr/bin/env python3

import argparse
import os
import sys
import logging
import pandas as pd
import gzip

logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

def parse_args(args=None):
    description= 'Checks to ensure the file has content. Removes the file from the samplesheet if there is no data.'
    epilog = 'Example usage: python3 file_size_check.py <SAMPLESHEET>'
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

    logging.debug("Setting full path up")
    path_only = path_only + "/"

    return path_only

def check_file_bytes(file_path):

    with gzip.open(file_path, 'rb') as infile:

        logging.debug(f"Try to read one byte from {infile}")
        try:

            logging.debug(f"{infile} is empty")
            return infile.read(1) == b''

        except OSError:
            logging.info(f"Error reading file: {file_path}")
            return True


def remove_from_samplesheet(list_files, samplesheet):

    outfile = "final_" + os.path.basename(samplesheet)
    removed = "removed_samples_" + os.path.basename(samplesheet)

    with open(samplesheet, "r") as file, open(outfile, "w") as out, open(removed, "w") as rm:
        for line in file:
            if any(file in line for file in list_files):
                rm.write(line)
            else:
                out.write(line)

    return out, rm

def main(args=None):
    args = parse_args(args)

    file_path = get_file_path(args.samplesheet)
    files_to_check_bytes = check_file_bytes(file_path)
    remove_from_samplesheet(files_to_check_bytes, args.samplesheet)

if __name__ == "__main__":
    sys.exit(main())