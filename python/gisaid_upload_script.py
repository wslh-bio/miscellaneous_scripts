#!/usr/bin/env/ python3

import argparse
import logging
import sys
import os
import json
import pandas as pd

from datetime import datetime
from Bio import SeqIO

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

def determine_output_names():

    upload_date = datetime.today().strftime('%Y-%m-%d')
    output_file_name = upload_date + "_EpiCoV_BulkUpload.csv"
    fn_output_name = upload_date + "_upload.fasta"

    return output_file_name, fn_output_name

def process_csv_files(csv_dir, json_data, masterlog, fasta_name):

    all_data = []

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
                    id = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'Sequencing ID']

                all_data.append({
                    'Sample ID': sample,
                    'DOC': doc.iloc[0] if not doc.empty else None,
                    'County': county.iloc[0] if not county.empty else None,
                    'Sequencing ID' : id.iloc[0] if not id.empty else None
                })

    for sample in all_data:
        sample['fn'] = fasta_name

    return all_data

def joining_information(ml_data, json_data, name):

    date = datetime.today().strftime('%Y')

    logging.debug("Starting to merge data frames.")
    ml = pd.DataFrame(ml_data)

    logging.debug("Setting up json info")
    static_columns = json_data.get('static_columns', [])
    static_columns = pd.DataFrame(static_columns, index=[0])

    column_order = json_data.get('required_columns', [])

    logging.debug("Merging static columns and ml data")
    merged = pd.DataFrame.merge(ml, static_columns, how='cross')

    logging.debug("Updating with proper formatting.")
    merged['covv_location'] = merged['covv_location'].fillna("")
    merged['covv_location'] = merged['covv_location'] + " / " + merged['County'].str.capitalize()
    merged['covv_location'] = merged['covv_location'].str.lstrip("/")
    merged['covv_virus_name'] = merged['covv_virus_name'] + ml['Sequencing ID'] + "/" + date


    logging.debug("Dropping columns.")
    merged = merged.drop(columns=['County'])
    merged = merged.drop(columns=['Sequencing ID'])
    merged = merged.drop(columns=['Sample ID'])

    merged.reindex(columns=column_order)

    # merged.to_csv(name, index=False)

    return merged

def write_output_file(output_file, json, data):

    required_columns = json.get('required_columns', [])

    # Add missing columns as NaN
    for header in required_columns:
        if header not in data.columns:
            logging.warning(f"Adding missing column: {header}")
            data[header] = None  # Or use pd.NA for explicitly Pandas' NA value

    # Reorder columns to match the required order
    data = data[required_columns]

    # Write the reordered DataFrame to the output file
    data.to_csv(output_file, index=False)

    # out.to_csv(output_file, sep='\t')

def write_fasta_file(fasta_name):

    pass

def main(args=None):
    args = parse_args(args)

    json_data = load_json(args.json_file)
    output_file_name, fasta_name = determine_output_names()
    masterlog_data = process_csv_files(args.path_to_output_csvs, json_data, args.masterlog, fasta_name)
    final_data = joining_information(masterlog_data, json_data, output_file_name)
    write_output_file(output_file_name, json_data, final_data)
    write_fasta_file(fasta_name)

if __name__ == "__main__":
    sys.exit(main())