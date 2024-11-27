#!/usr/bin/env/ python3

import argparse
import logging
import sys
import os
import json
import pandas as pd

from datetime import datetime

logging.basicConfig(level = logging.DEBUG, format = "%(levelname)s : %(message)s", force = True)

def parse_args(args=None):
    description= ""
    epilog = "Example usage: python3 gisaid_upload_script.py <path to reports> <json file> <masterlog>"
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument("path_to_output_csvs",
        help="Path to compiled viral recon reports.")
    parser.add_argument("json_file",
        help="Path to json file with static values.")
    parser.add_argument("masterlog",
        help="Path to virus masterlog.")
    return parser.parse_args(args)

def load_json(json_file):

    logging.debug("Opening and reading json file.")
    with open(json_file, 'r') as f:
        json_data = json.load(f)

    return json_data

def process_csv_files(csv_dir, json_data, masterlog):

    all_data = []

    required_columns = json_data.get('required_columns', [])
    logging.debug(f"{required_columns}")

    df_masterlog = pd.read_csv(masterlog, on_bad_lines='skip', sep="\t")

    for filename in os.listdir(csv_dir):

        logging.debug(f"Processing {filename}")
        csv_path = os.path.join(csv_dir, filename)
        df_csv = pd.read_csv(csv_path)

        logging.debug("Filtering to include only passing samples.")
        passing_samples = df_csv[df_csv['WSLH_qc'] == 'pass']['sample_id']
        logging.debug(f"From file {filename}\n{passing_samples}")

        column_mappings = json_data.get('column_mappings', {})

    for required_name, report_name in column_mappings.items():
        logging.debug(f"The key is {required_name}. The value is {report_name}.")

        if report_name in df_masterlog.columns:
            logging.debug(f"Found column '{report_name}' in df_masterlog.")

            for sample in passing_samples:
                output = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, report_name]

                if not output.empty:
                    doc = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'DOC']
                    county = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'Pt County']

                all_data.append({
                    'Sample ID': sample,
                    'DOC': doc.iloc[0] if not doc.empty else None,
                    'County': county.iloc[0] if not county.empty else None
                })

    return all_data

def joining_information(ml_data, json_data):

    logging.info("Starting to merge data frames.")
    ml = pd.DataFrame(ml_data)

    static_columns = json_data.get('static_columns', [])

    print(ml)
    print(static_columns)

def determine_output_name():

    upload_date = datetime.today().strftime('%Y-%m-%d')
    output_file_name = upload_date + "_EpiCoV_BulkUpload.csv"

    return output_file_name

# 7. Write the combined data to an output CSV file
def write_output_file(output_file, final_data):

    pass
    # out.to_csv(output_file, sep='\t')

def main(args=None):
    args = parse_args(args)

    json_data = load_json(args.json_file)
    masterlog_data = process_csv_files(args.path_to_output_csvs, json_data, args.masterlog)
    final_data = joining_information(masterlog_data, json_data)
    output_file_name = determine_output_name()
    write_output_file(output_file_name, final_data)

if __name__ == "__main__":
    sys.exit(main())


    # def create_column_mapping(csv_columns, required_columns, json_data):
#     logging.debug("Creating a function to map CSV columns to required columns.")
#     column_mapping = {}

#     # Get the 'column_mappings' dictionary from the JSON data
#     column_mappings = json_data.get('column_mappings', {})

#     # Iterate through the keys (required columns) in 'column_mappings'
#     for required_column, csv_column_name in column_mappings.items():
#         # Check if the csv_column_name exists in the CSV columns
#         if csv_column_name in csv_columns:
#             column_mapping[csv_column_name] = required_column
#         else:
#             logging.warning(f"CSV column for '{required_column}' not found: {csv_column_name}")

#     return column_mapping
