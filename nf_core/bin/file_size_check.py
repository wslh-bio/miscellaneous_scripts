#!/usr/bin/env python3

import argparse
import logging
import sys
import boto3
import gzip

import pandas as pd

from io import BytesIO

logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

logging.debug("Initializing s3")
s3 = boto3.client('s3')

def parse_args(args=None):
    description= 'Checks to ensure the file has content. Removes the file from the samplesheet if there is no data.'
    epilog = 'Example usage: python3 file_size_check.py <SAMPLESHEET>'
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument('samplesheet',
        help='Samplesheet to check.')
    return parser.parse_args(args)

def is_s3_gzipped_file_empty(uri):

    logging.debug("Get bucket and prefix information")
    bucket_name, key = uri.replace("s3://", "").split("/", 1)

    logging.debug("Getting s3 object")
    response = s3.get_object(Bucket=bucket_name, Key=key)

    with gzip.GzipFile(fileobj=BytesIO(response['Body'].read())) as infile:

        logging.debug("Checking if the file has data")
        return infile.read(1) == b''

def look_at_samplesheet(samplesheet):

    ss_df = pd.read_csv(samplesheet, header=0)

    filtered_samplesheet = ss_df[
    ss_df['fastq_1'].apply(lambda uri: not is_s3_gzipped_file_empty(uri)) &
    ss_df.apply(lambda row: (row['single_end'] or pd.isna(row['fastq_2']) or not is_s3_gzipped_file_empty(row['fastq_2'])), axis=1)
    ]

    final_file = filtered_samplesheet.to_csv('filtered_samplesheet.csv', index=False)

    return final_file

def main(args=None):
    args = parse_args(args)

    look_at_samplesheet(args.samplesheet)

if __name__ == "__main__":
    sys.exit(main())