#!/usr/bin/env/ python3

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(level = logging.DEBUG, format = '%(levelname)s : %(message)s', force = True)

def parse_args(args=None):
    description= 'Pull consensus sequences from viralrecon WSLH report.'
    epilog = 'Example usage: python3 gisaid_upload_script.py <> <>'
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    # parser.add_argument('',
    #     help='')
    # parser.add_argument('',
    #     help='')
    return parser.parse_args(args)

def make_bulk_file():
    df = pd.DataFrame(columns=
                      ['submitter',
                      'fn',
                      'covv_virus_name',
                      'covv_type',
                      'covv_passage',
                      'covv_collection_date',
                      'covv_location',
                      'covv_add_location',
                      'covv_host',
                      'covv_add_host_info',
                      'covv_sampling_strategy',
                      'covv_gender',
                      'covv_patient_age',
                      'covv_patient_status',
                      'covv_specimen',
                      'covv_outbreak',
                      'covv_last_vaccinated',
                      'covv_treatment',
                      'covv_seq_technology',
                      'covv_assembly_method',
                      'covv_coverage',
                      'covv_orig_lab',
                      'covv_orig_lab_addr',
                      'covv_provider_sample_id',
                      'covv_subm_lab',
                      'covv_subm_lab_addr',
                      'covv_subm_sample_id',
                      'covv_authors',
                      'covv_comment',
                      'comment_type',
                      'covv_consortium']
    )

    df.to_csv("bulk.csv", index=False)

def main(args=None):
    args = parse_args(args)
    make_bulk_file()

if __name__ == "__main__":
    sys.exit(main())