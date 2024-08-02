#!/usr/bin/env python3

import argparse
from datetime import datetime
import logging
import sys
import os
import pandas as pd

def parse_args(args=None):
  Description='Pull consensus sequences from viralrecon WSLH report.'

  parser = argparse.ArgumentParser(description=Description)
  parser.add_argument('wslh_report',
                      help='Report to be get consensus IDs from.')
  parser.add_argument('path_to_sequences',
                      help='Path to get consensus sequences.')
  return parser.parse_args(args)

def process_report(report):
    passing_ids = []

    data = pd.read_csv(os.path.abspath(report),sep=',',index_col="sample_id").sort_index()
    data = data.reindex(sorted(data.columns),axis=1)

    passing_ids = data.loc[data['WSLH_qc'] == 'pass', 'sample'].tolist()

    return passing_ids

def make_folder_path():

    logging.debug("Getting date for file structure.")

    upload_date = datetime.today().strftime('%Y-%m-%d')
    folder_path = upload_date + "/genomes/"

    return folder_path

def pull_consensus_seqs(path_to_seqs, ids):
    for fasta in path_to_seqs:
        for id in ids:
            if id in fasta:
                print(fasta) 


def main(args=None):
    args = parse_args(args)
    folder_path = make_folder_path()
    passing_ids = process_report(args.wslh_report)

    
if __name__ == "__main__":
    sys.exit(main())