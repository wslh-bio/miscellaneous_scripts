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
    epilog = "Example usage: python3 gisaid_upload_script.py <> <>"
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument("path_to_output_csvs",
        help="")
    parser.add_argument("json_file",
        help="Path to json file with static values.")
    return parser.parse_args(args)

def load_json(json_file):

    logging.debug("Opening and reading json file.")
    with open(json_file, 'r') as f:
        json_data = json.load(f)

    return json_data

# 2. Create a function to map CSV columns to required columns
def create_column_mapping(csv_columns, required_columns, json_data):
    logging.debug("Creating a fuction to map CSV columns to all of the required columns.")
    column_mapping = {}

    for required_column in required_columns:
        # If there's a mapping for this required column in the JSON
        if required_column in json_data.get('column_mappings', {}):
            # Map the CSV column to the required column
            csv_column_name = json_data['column_mappings'].get(required_column, None)
            if csv_column_name and csv_column_name in csv_columns:
                column_mapping[csv_column_name] = required_column

    return column_mapping

# 3. Process the CSV files and filter data based on the "qc" column
def process_csv_files(csv_dir, json_data):
    # Create a list to store all the processed data
    all_data = []

    # Get the required columns from the JSON
    required_columns = json_data.get('required_columns', [])

    # Iterate over all CSV files in the directory
    for filename in os.listdir(csv_dir):
        if filename.endswith('.csv'):
            csv_path = os.path.join(csv_dir, filename)
            # Load the CSV file into a pandas DataFrame
            df = pd.read_csv(csv_path)

            # 4. Filter rows where the "qc" column has value "pass"
            passing_samples = df[df['WSLH_qc'] == 'pass']

            # 5. Create a mapping of CSV columns to required columns
            column_mapping = create_column_mapping(df.columns, required_columns, json_data)

            # 6. Rename the columns of the DataFrame based on the mapping
            passing_samples_renamed = passing_samples.rename(columns=column_mapping)

            # Extract only the required columns based on the mapping
            passing_samples_filtered = passing_samples_renamed[required_columns]

            # Add static data from the JSON (assuming it is a dict of values)
            for column in json_data.get('static_columns', {}):
                passing_samples_filtered[column] = json_data['static_columns'][column]

            # Append the processed data
            all_data.append(passing_samples_filtered)

    # Concatenate all the processed data into one DataFrame
    final_data = pd.concat(all_data, ignore_index=True)
    return final_data

def determine_output_name():
    upload_date = datetime.today().strftime('%Y-%m-%d')
    output_file_name = upload_date + "_EpiCoV_BulkUpload.csv"

    return output_file_name

# 7. Write the combined data to an output CSV file
def write_output_file(output_file, final_data):
    final_data.to_csv(output_file, index=False)

def main(args=None):
    args = parse_args(args)

    # Load the static data from the JSON
    json_data = load_json(args.json_file)

    # Process the CSV files and extract the required data
    final_data = process_csv_files(args.path_to_output_csvs, json_data)

    output_file_name = determine_output_name()

    # Write the final data to an output CSV file
    write_output_file(output_file_name, final_data)

if __name__ == "__main__":
    sys.exit(main())