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

logging.basicConfig(level = logging.DEBUG, format = "%(levelname)s : %(message)s", force = True)

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

    logging.debug("Getting date for file structure.")

    upload_date = datetime.today().strftime('%Y-%m-%d')
    batch_name = sequences_uri.split("/")[-2]
    folder_path = upload_date + "/genomes/" + batch_name

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
            logging.info(f"Successfully downloaded {id_key}")
        except s3.exceptions.NoSuchKey:
            logging.error(f"File not found for {id_key}")
        except Exception as e:
            logging.error(f"Downloading {id_key} failed: {e}")

def determine_output_name(date):

    output_file_name = date + "_upload.fasta"

    return output_file_name

def create_fasta_file(dictionary, path, output_name):

    for filename in os.listdir(path):
        full_path = "./"+path+"/"+filename
        for record in SeqIO.parse(full_path, "fasta"):
            if os.path.exists(output_name):
                with open(output_name, "a") as out:
                    SeqIO.write(record, out, "fasta")
            else:
                with open(output_name, "w") as out:
                    SeqIO.write(record, out, "fasta")
    sys.exit(0)
        # actual_path = "/"+ path + filename
        # with open(actual_path, "r"):
        #     logging.debug(f"Processing {filename}")
        #     records = SeqIO.parse(actual_path, "fasta")
        #     print(records)
        #     sys.exit(0)

def main(args=None):
    args = parse_args(args)
    for uri in args.wslh_reports:
        path, date = make_folder_path(uri)
        matching_sequence_uri = match_uris(uri, args.uris_to_sequences)
        filtered_passing_samples, nonfiltered_passing_samples = process_reports_for_passing_samples(uri)
        dictionary_of_deidentified = get_deidentified_ids(args.masterlog, filtered_passing_samples)
        pull_consensus_seqs(matching_sequence_uri, nonfiltered_passing_samples, path)
        output = determine_output_name(date)
        create_fasta_file(dictionary_of_deidentified, path, output)


if __name__ == "__main__":
    sys.exit(main())