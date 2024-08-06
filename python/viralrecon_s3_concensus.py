#!/usr/bin/env python3

import argparse
import logging
import sys
import boto3
import os

import pandas as pd

from datetime import datetime
from io import StringIO

logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

def parse_args(args=None):
    Description=('Pull consensus sequences from viralrecon WSLH report.')
    Epilog = 'Example usage: python3 viralrecon_pull_consensus.py <WSLH_REPORT_URI> <FASTA_S3_URI>'
    parser = argparse.ArgumentParser(description=Description)
    parser.add_argument('wslh_report',
        help='URI for report to get consensus IDs from.')
    parser.add_argument('uri_to_sequences',
        help='URI for directory holding consensus sequences.')
    return parser.parse_args(args)

def make_folder_path():

    logging.debug("Getting date for file structure.")

    upload_date = datetime.today().strftime('%Y-%m-%d')
    folder_path = upload_date + "/genomes/"

    return folder_path, upload_date

def process_report(s3_report_uri):

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

    return passing_sample_names

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

def main(args=None):
    args = parse_args(args)
    folder_path, date = make_folder_path()
    passing_ids = process_report(args.wslh_report)
    pull_consensus_seqs(args.uri_to_sequences, passing_ids, folder_path)

if __name__ == "__main__":
    sys.exit(main())