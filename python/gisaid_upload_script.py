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

def determine_output_name():

    logging.debug("Creating file names based on date.")
    upload_date = datetime.today().strftime('%Y-%m-%d')
    output_file_name = upload_date + "_EpiCoV_BulkUpload.csv"
    fasta_name = upload_date + "_upload.fasta"

    return output_file_name, fasta_name

def process_csv_files(csv_dir, json_data, masterlog):

    logging.debug("Setting up blank list to store information from ml")
    all_data = []

    df_masterlog = pd.read_csv(masterlog, on_bad_lines='skip', sep="\t")

    logging.debug("Going through each file in the directory.")
    for filename in os.listdir(csv_dir):

        logging.debug(f"Processing {filename}")
        csv_path = os.path.join(csv_dir, filename)
        df_csv = pd.read_csv(csv_path)

        logging.debug("Filtering to include only passing samples.")
        passing_samples = df_csv[df_csv['WSLH_qc'] == 'pass']['sample_id']
        logging.debug(f"From file {filename}\n{passing_samples}")

        logging.debug("Reading in information for mapping columns to each other from masterlog and output file columns.")
        column_mappings = json_data.get('column_mappings', {})

    for required_name, report_name in column_mappings.items():
        logging.debug(f"The key is {required_name}. The value is {report_name}.")

        if report_name in df_masterlog.columns:
            logging.debug(f"Found column '{report_name}' in df_masterlog.")

            for sample in passing_samples:
                output = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, report_name]

                logging.debug("If output is not empty, save information to all_data list")
                if not output.empty:
                    doc = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'DOC']
                    seq_id = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'Sequencing ID']

                all_data.append({
                    'Sample ID': sample,
                    'DOC': doc.iloc[0] if not doc.empty else None,
                    'Sequencing ID' : seq_id.iloc[0] if not seq_id.empty else None
                })

    with open('sequencing_id.csv', 'w') as f:
        for line in all_data:
            f.write(f"{line}\n")

    return all_data

def joining_information(ml_data, json_data, fasta_name):

    logging.debug("Setting up year for covv_virus_name columns")
    date = datetime.today().strftime('%Y')

    logging.debug("Starting to merge data frames.")
    ml = pd.DataFrame(ml_data)

    logging.debug("Setting up json info")
    static_columns = json_data.get('static_columns', [])
    static_columns = pd.DataFrame(static_columns, index=[0])

    logging.debug("Merging static columns and ml data")
    merged = pd.DataFrame.merge(ml, static_columns, how='cross')

    logging.debug("Reformatting covv virus name")
    merged['covv_virus_name'] = merged['covv_virus_name'] + ml['Sequencing ID'] + "/" + date

    merged['fn'] = fasta_name

    logging.debug("Reformatting and renaming DOC to covv collection date.")
    merged = merged.rename(columns={"DOC":"covv_collection_date"})
    merged['covv_collection_date'] = pd.to_datetime(merged['covv_collection_date'], format='%m/%d/%Y').dt.strftime('%Y-%m-%d')

    logging.debug("Dropping columns.")
    merged = merged.drop(columns=['Sequencing ID'])
    merged = merged.drop(columns=['Sample ID'])

    return merged

def write_output_file(output_file, json, data):

    required_columns = json.get('required_columns', [])

    logging.debug("Add missing columns based on the required columns in the json file")
    for header in required_columns:
        if header not in data.columns:
            logging.warning(f"Adding missing column: {header}")
            data[header] = None

    logging.debug("Reorder columns to match the required order in json file")
    data = data[required_columns]

    logging.debug("Write the reordered DataFrame to the output file")
    data.to_csv(output_file, index=False)

def main(args=None):
    args = parse_args(args)

    json_data = load_json(args.json_file)
    output_file_name, fasta_name = determine_output_name()
    masterlog_data = process_csv_files(args.path_to_output_csvs, json_data, args.masterlog)
    final_data = joining_information(masterlog_data, json_data, fasta_name)
    write_output_file(output_file_name, json_data, final_data)

if __name__ == "__main__":
    sys.exit(main())