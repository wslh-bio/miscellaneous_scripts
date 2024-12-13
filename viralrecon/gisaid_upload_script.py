#!/usr/bin/env/ python3

import argparse
import logging
import sys
import os
import json
import pandas as pd

from datetime import datetime
from Bio import SeqIO

logging.basicConfig(level = logging.INFO, format = "%(levelname)s : %(message)s", force = True)

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
    logging.debug("Setting up blank dictionary to store information from masterlog.")
    all_data = pd.DataFrame()
    # all_data.columns = ['Sample ID','DOC','Sequencing ID']

    logging.debug("Reading in information for mapping columns to each other from masterlog and output file columns.")
    column_mappings = json_data.get('column_mappings', {})

    # Read masterlog file
    df_masterlog = pd.read_csv(masterlog, on_bad_lines='skip', sep="\t")

    logging.debug("Going through each file in the directory.")
    for filename in os.listdir(csv_dir):
        logging.info(f"Processing {filename}")
        csv_path = os.path.join(csv_dir, filename)
        df_csv = pd.read_csv(csv_path)

        logging.debug("Filtering to include only passing samples.")
        passing_samples = df_csv[df_csv['WSLH_qc'] == 'pass']['sample_id']
        logging.debug(f"From file {filename}\n{passing_samples}")

        for required_name, report_name in column_mappings.items():
            logging.debug(f"The key is {required_name}. The value is {report_name}.")

            if report_name in df_masterlog.columns:
                logging.debug(f"Found column '{report_name}' in df_masterlog.")

                for sample in passing_samples:

                    output = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, report_name]
                    if output.empty:
                        if os.path.exists("Missing_samples_from_masterlog.txt"):
                            with open("Missing_samples_from_masterlog.txt", "a") as f:
                                f.write(f"{sample}\n")
                        else:
                            with open("Missing_samples_from_masterlog.txt", "w") as f:
                                f.write(f"Missing samples \n{sample}\n" )
                    else:
                        logging.debug("If output is not empty, save information to all_data list")
                        doc = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'DOC']
                        seq_id = df_masterlog.loc[df_masterlog['WSLH ID'] == sample, 'Sequencing ID']
                    new_row={
                        'Sample ID':sample,
                        'DOC':doc.iloc[0] if not doc.empty else None,
                        'Sequencing ID':seq_id.iloc[0] if not seq_id.empty else None
                    }

                    if all_data.isin([sample]).any().any():
                        pass
                    else:
                        all_data = pd.concat([all_data, pd.DataFrame([new_row])], ignore_index=False)

    return all_data

def joining_information(ml_data, json_data, fasta_name):

    logging.debug("Starting to merge data frames.")

    logging.debug("Setting up json info")
    static_columns = json_data.get('static_columns', [])
    static_columns = pd.DataFrame(static_columns, index=[0])

    logging.debug("Merging static columns and ml data")
    merged = pd.DataFrame.merge(ml_data, static_columns, how='cross')

    logging.debug("Reformatting and renaming DOC to covv collection date.")
    merged = merged.rename(columns={"DOC":"covv_collection_date"})
    merged['covv_collection_date'] = pd.to_datetime(merged['covv_collection_date'], format='%m/%d/%Y').dt.strftime('%Y-%m-%d')

    logging.debug("Reformatting covv virus name")
    logging.debug("Checking to see if anything is duplicated")
    if merged.index.duplicated().any():
        merged = merged.reset_index(drop=True)
    if ml_data.index.duplicated().any():
        ml_data = ml_data.reset_index(drop=True)

    logging.debug("Setting up DOC to be year")
    ml_data['DOC'] = ml_data['DOC'].str[-4:]

    logging.debug("Makes sure indices align")
    merged = merged.reset_index(drop=True)
    ml_data = ml_data.reset_index(drop=True)

    logging.debug("Setting up covv_virus_name column with correct format")
    merged['covv_virus_name'] = merged['covv_virus_name'] + ml_data['Sequencing ID'] + "/" + ml_data['DOC']

    logging.debug("Letting fasta name = column fn")
    merged['fn'] = fasta_name

    logging.debug("Dropping columns.")
    merged = merged.drop(columns=['Sequencing ID'])
    merged = merged.drop(columns=['Sample ID'])

    return merged

def write_output_file(output_file, json, data):

    required_columns = json.get('required_columns', [])

    logging.debug("Add missing columns based on the required columns in the json file")
    for header in required_columns:
        if header not in data.columns:
            logging.debug(f"Adding missing column to dataframe: {header}")
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
    if os.path.exists("Missing_samples_from_masterlog.txt"):
        logging.critical("There are missing samples from the masterlog. Please check the missing samples txt file for which samples are missing.\nStopping creation of bulk upload file.")
    final_data = joining_information(masterlog_data, json_data, fasta_name)
    write_output_file(output_file_name, json_data, final_data)

if __name__ == "__main__":
    sys.exit(main())