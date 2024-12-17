#!/usr/bin/env python3

import argparse
import logging
import sys
import boto3
import os
import re


import pandas as pd

from datetime import datetime
from io import StringIO
from Bio import SeqIO

logging.basicConfig(level = logging.INFO, format = "%(levelname)s : %(message)s", force = True)

def parse_args(args=None):
    description= 'Run viralrecon params to pull consensus sequences.'
    epilog = 'Example usage: python3 viralrecon_pull_consensus.py <WSLH_REPORT_URI> <FASTA_S3_URI>'
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument('wslh_reports',
                        nargs='+',
        help='URIs for reports to get passing IDs.')
    parser.add_argument('--uris_to_sequences',
                        '-f',
                        nargs='+',
                        required=True,
        help='URI to consensus sequences')
    parser.add_argument('--masterlog',
                        '-m',
                        required=True,
        help="Masterlog with deidentified ids.")
    return parser.parse_args(args)

def make_folder_path(sequences_uri):

    pattern = r'\d{2}-COVIDSEQ\d{2}(?:_\d{2}|-\d{2})?'

    logging.debug("Getting date for file structure.")

    upload_date = datetime.today().strftime('%Y-%m-%d')
    filtered_batch_name = re.search(pattern, sequences_uri)
    folder_path = upload_date + "/genomes/" + filtered_batch_name.group(0)

    return folder_path, upload_date

def match_uris(report, sequences):

    pattern = r'\d{2}-COVIDSEQ(\d{2}[-_]?\d{2}|\d{2})'
    report_name = report.split("/")[-1]
    report_batch = re.search(pattern, report_name)
    report_batch_number = report_batch.group(1)

    for uri in sequences:
        sequence_name = uri.split("/")[-2]
        seq_batch = re.search(pattern, sequence_name)
        seq_batch_number = seq_batch.group(1)
        if report_batch_number == seq_batch_number:
            return uri

def process_reports_for_passing_samples(s3_report_uri):

    logging.debug("Initializing s3 client")
    s3 = boto3.client('s3')

    logging.debug("Get bucket and prefix information")
    bucket_name, key = s3_report_uri.replace("s3://", "").split("/", 1)

    logging.debug("Getting s3 object")
    response = s3.get_object(Bucket=bucket_name, Key=key)

    logging.debug("Storing content of s3 object")
    csv_content = response['Body'].read().decode('utf-8')

    logging.debug("Using pandas to extract samples that pass")
    df = pd.read_csv(StringIO(csv_content))
    passing_samples = df[df.iloc[:,1].str.lower() == "pass"]
    passing_sample_names = passing_samples.iloc[:,-1].tolist()

    for sample in passing_sample_names:
        if "Q" in sample:
            passing_sample_names.remove(sample)

    sep = "_"
    filtered_names = []
    nonfiltered_names = passing_sample_names
    for sample in passing_sample_names:
        filtered_names.append(sample.split(sep, 1)[0])

    return filtered_names, nonfiltered_names

def get_deidentified_ids(masterlog, passing_samples):

    df_masterlog = pd.read_csv(masterlog, on_bad_lines='skip', sep="\t")

    filtered_masterlog = df_masterlog[df_masterlog["WSLH ID"].isin(passing_samples)]
    alternate_id_dict = filtered_masterlog.set_index('WSLH ID')['Sequencing ID'].to_dict()

    return alternate_id_dict

def pull_consensus_seqs(uri_to_seqs, ids, output_path):
    s3 = boto3.client('s3')

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    bucket_name, key = uri_to_seqs.replace("s3://", "").split("/", 1)

    logging.debug(f"This is bucket: {bucket_name}")
    logging.debug(f"This is key: {key}")
    logging.debug(f"This is output path: {output_path}")

    for id in ids:

        id_key = f"{key}/{id}.consensus.fa"
        id_key = id_key.replace("//", "/")
        local_file_path = os.path.join(output_path, f"{id}.consensus.fa")

        try:
            s3.download_file(bucket_name, id_key, local_file_path)
            logging.debug(f"Successfully downloaded {id_key}")
        except s3.exceptions.NoSuchKey:
            logging.error(f"File not found for {id_key}")
        except Exception as e:
            logging.error(f"Downloading {id_key} failed: {e}")

def determine_output_name(date):

    output_file_name = date + "_upload.fasta"

    return output_file_name, date

def create_fasta_file(dictionary, path, output_name, date):
    # Get the root directory to walk through
    root_dir = "/".join(path.split("/")[:2])
    records = []  # List to store all records across all files

    # Traverse through the root directory and its subdirectories
    for root, dirs, files in os.walk(root_dir):
        print(f"Root {root}\ndir {dirs}\n files {files}")
        for file in files:
            print(file)
            full_path = os.path.join(root, file)  # Correctly construct full path
            logging.debug(f"Processing fasta file: {full_path}")

            with open(full_path, "r") as infile:
                # Parse the fasta file and update record IDs
                for record in SeqIO.parse(infile, "fasta"):
                    for filtered_name, alternative_name in dictionary.items():
                        if filtered_name in record.id:
                            record.id = f"hCoV-19/USA/{alternative_name}/{date[:4]}"
                            record.description = alternative_name
                            print(record)
                    records.append(record)  # Add updated records to the list

    # Write all collected records to the output fasta file
    output_name = "test.fasta"
    logging.debug(f"Writing all records to output fasta file: {output_name}")
    if records:  # Only write if records exist
        with open(output_name, "w") as outfile:
            SeqIO.write(records, outfile, "fasta")
    else:
        logging.warning("No records were found to write to the output file.")

    return output_name

def sanitize_fasta_file(fasta, output_name):
    with open(fasta, "r") as input, open(output_name, "w") as output:
        for record in SeqIO.parse(input, "fasta"):
            record.id = record.id.replace(record.id, record.id.split(" ")[0])
            record.description = ""
            SeqIO.write(record, output, "fasta")

    os.remove(fasta)

def main(args=None):
    args = parse_args(args)

    # Persistent lists to collect all passing samples
    all_filtered_passing_samples = []
    all_nonfiltered_passing_samples = []

    for uri in args.wslh_reports:
        path, date = make_folder_path(uri)
        matching_sequence_uri = match_uris(uri, args.uris_to_sequences)

        # Process current URI and append results to persistent lists
        filtered_passing_samples, nonfiltered_passing_samples = process_reports_for_passing_samples(uri)
        all_filtered_passing_samples.extend(filtered_passing_samples)
        all_nonfiltered_passing_samples.extend(nonfiltered_passing_samples)

        # Fetch sequences (but don't write output yet)
        pull_consensus_seqs(matching_sequence_uri, nonfiltered_passing_samples, path)

    # Combine all passing samples and create the final FASTA
    if all_filtered_passing_samples:
        logging.debug("Creating the final FASTA file with all passing samples.")
        
        # Combine all deidentified IDs across all URIs
        dictionary_of_deidentified = get_deidentified_ids(args.masterlog, all_filtered_passing_samples)
        logging.debug(f"Total of dictionary: {len(dictionary_of_deidentified)}")

        # Determine final output name
        output_name, date = determine_output_name(date)  # Use the last 'date' for naming purposes
        
        # Create the FASTA file using the full combined list
        fasta = create_fasta_file(dictionary_of_deidentified, path, output_name, date)
        sanitize_fasta_file(fasta, output_name)

        logging.info("Final FASTA file written successfully.")
    else:
        logging.warning("No passing samples were found. No FASTA file was created.")

    # Log summary of results
    logging.debug(f"Total filtered passing samples: {len(all_filtered_passing_samples)}")
    logging.debug(f"Total non-filtered passing samples: {len(all_nonfiltered_passing_samples)}")


if __name__ == "__main__":
    sys.exit(main())