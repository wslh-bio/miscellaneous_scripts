#!/usr/bin/env python3

import argparse
import logging
import sys
import os
import shutil

import pandas as pd

from datetime import datetime
from io import StringIO

logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

def parse_args(args=None):
    description= 'Pull consensus sequences from viralrecon WSLH report.'
    epilog = 'Example usage: python3 viralrecon_pull_consensus.py <LOCAL_WSLH_REPORT> <LOCAL_CONSENSUS_DIR> <BATCH_NAME>'
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument('wslh_report',
        help='Report to be get consensus IDs from.')
    parser.add_argument('consensus_dir',
        help='Path to directory holding consensus sequences.')
    parser.add_argument('batch_name',
        help='Name of the batch being analyzed.')
    return parser.parse_args(args)

def make_folder_path(batch_name):

    logging.debug("Getting date for file structure.")

    upload_date = datetime.today().strftime('%Y-%m-%d')

    logging.debug("Creating folder path with batch name.")
    folder_path = upload_date + "/genomes/" + batch_name

    return folder_path

def process_report(report):

    logging.debug("Using pandas to extract samples that pass")
    df = pd.read_csv(report)
    passing_samples = df[df.iloc[:,1].str.lower() == "pass"]
    passing_sample_names = passing_samples.iloc[:,-1].tolist()

    for sample in passing_sample_names:

        if "Q" in sample:
            passing_sample_names.remove(sample)

    return passing_sample_names

def pull_consensus_seqs(consensus_path, ids, output_path):

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    logging.debug("Copying files from source directory to destination directory.")
    for filename in os.listdir(consensus_path):
        src = os.path.join(consensus_path, filename)
        for id in ids:
            id = f"{id}.consensus.fa"
            if id in filename:
                dst = os.path.join(output_path, filename)
                shutil.copyfile(src, dst)

def main(args=None):
    args = parse_args(args)

    logging.info("Beginning to process WSLH report")
    folder_path = make_folder_path(args.batch_name)
    passing_ids = process_report(args.wslh_report)
    pull_consensus_seqs(args.consensus_dir, passing_ids, folder_path)
    logging.info("Finished processing report.")
    
if __name__ == "__main__":
    sys.exit(main())