#!/usr/bin/env/ python3

import argparse
import logging
import sys
import os
import json

import pandas as pd

logging.basicConfig(level = logging.DEBUG, format = "%(levelname)s : %(message)s", force = True)

def parse_args(args=None):
    description= ""
    epilog = "Example usage: python3 gisaid_upload_script.py <> <>"
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    # parser.add_argument("path_to_output_csvs",
    #     help="")
    parser.add_argument("json_file",
        help="Path to json file with static values.")
    return parser.parse_args(args)

def use_json(input_file):

    with open(input_file, "r") as file:

        static_data = json.load(file)

        return static_data

def fill_out_bulk_file(path):

    for file in path:

        filepath = os.path.join(path, file)
        df_file = pd.read_csv(filepath)
        filtered = df_file[df_file["WSLH_qc"] == "pass" ] 
        filtered.to_csv("filtered.csv", index=False)

def main(args=None):
    args = parse_args(args)

    #make_bulk_file()
    use_json(args.json_file)
    #fill_out_bulk_file(args.path_to_output_csvs)

if __name__ == "__main__":
    sys.exit(main())