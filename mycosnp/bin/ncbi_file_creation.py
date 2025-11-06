#!/usr/bin/env python

import sys
import logging
import argparse

import numpy as np
import pandas as pd

logging.basicConfig(level = logging.DEBUG, format = '%(levelname)s : %(message)s')

def pass_fail (qc_stats):

    logging.debug("Read csv files")
    qc = pd.read_csv(qc_stats, sep= '\t')

    logging.debug('Remove "%" from "GC content after trimming"')
    qc['GC After Trimming normalized'] = qc['GC After Trimming'].str.rstrip('%').astype(float)

    logging.debug("Define pass fail criteria")
    pass_fail_criteria = (
        (qc['GC After Trimming normalized'] >= 42) &
        (qc['GC After Trimming normalized'] <= 47.5) &
        (qc['Average Q Score After Trimming'] >= 28) &
        (qc['Mean Coverage Depth'] >= 20))

    logging.debug("Assign pass if sample meets criteria above")
    qc.loc[(pass_fail_criteria), 'pass/fail'] = 'pass'

    logging.debug("Assign fail if sample does not meet criteria above")
    qc.loc[(~pass_fail_criteria), 'pass/fail'] = 'fail'

    return qc

def create_dataframes(metadata, qc_stats):

    logging.debug("Starting to create dataframes")
    meta_df = pd.read_csv(metadata, sep='\t')
    qc_df   = pd.DataFrame(qc_stats)

    return meta_df, qc_df

def merge_dataframes(metadata, qc):

    logging.debug("Clip 'Sample Name' and put into new column 'WSLH Specimen Number'")
    qc['WSLH Specimen Number'] = qc['Sample Name'].str.split('_').str[0].str.split('-').str[0].str.split('a').str[0]

    logging.debug("Create YYYY-MM for date of collection")
    metadata['collection_date'] = pd.to_datetime(metadata['Collection Date']).dt.strftime('%Y-%m')

    logging.debug("Create fastq file names")
    metadata['filename'] = metadata['HAI WGS ID']+'_R1_001.fastq.gz'
    metadata['filename2'] = metadata['HAI WGS ID']+'_R2_001.fastq.gz'

    logging.debug("Merge databases QC and Metadata")
    merged_df = pd.merge(qc, metadata, on='WSLH Specimen Number', how='inner')

    return merged_df

def create_ncbi_spreadsheets(all_data, run_name):

    df = pd.DataFrame(all_data)
    df_passed = df[df['pass/fail'] == 'pass']

    logging.debug("Create a dictionary with column names and corresponding biosample attributes for Biosample")
    biosample = {
        'sample_name': df_passed['HAI WGS ID'],
        'sample_title': "",
        'bioproject_accession': "PRJNA1085724",
        'organism': "Candida auris",
        'strain': "",
        'isolate': df_passed['HAI WGS ID'],
        'collected_by': "USA",
        'collection_date': df_passed['collection_date'],
        'geo_loc_name': "USA:Midwest",
        'host': "Homo sapiens",
        'host_disease': "not collected",
        'isolation_source': df_passed['Isolation Source'],
        'lat_lon': "38.00 N 97.00 W"
    }

    logging.debug("Create a dictionary with column names and corresponding data for SRA")
    sra = {
        'sample_name': df_passed['HAI WGS ID'],
        'library_ID': "",
        'title': "CDC Mycotic Diseases Branch Candida auris pathogen surveillance",
        'library_strategy': "WGS",
        'library_source': "Genomic",
        'library_selection': "RANDOM",
        'library_layout': "paired",
        'platform': "Illumina",
        'instrument_model': "Nextseq 2000",
        'design_description': "Illumina DNA prep",
        'filetype': "fastq",
        'filename': df_passed['filename'],
        'filename2': df_passed['filename2'],
        'filename3': "",
        'filename4': "",
        'assembly': "",
        'fasta_file': ""
    }

    logging.debug("Create DataFrame from the dictionary")
    df_biosample = pd.DataFrame(biosample)
    df_sra = pd.DataFrame(sra)

    logging.debug("Name files")
    biosample_file = run_name + '_biosample.tsv'
    sra_file = run_name + '_sra.tsv'
    passed_samples = run_name + '_passed_total_data.tsv'

    logging.debug("Export csv files")
    df_biosample.to_csv(biosample_file, sep='\t', index=False)
    df_sra.to_csv(sra_file, sep='\t', index=False)

    logging.debug("Export passed total data")
    df_passed.to_csv(passed_samples, sep='\t', index=False)
    df_passed.to_csv("pass.csv", columns=['WSLH Specimen Number', 'HAI WGS ID'], index=False)

class FileCreationNCBI(argparse.ArgumentParser):

    def error(self, message):
        self.print_help()
        sys.stderr.write(f'\nERROR DETECTED: {message}\n')

        sys.exit(1)

if __name__ == "__main__":
    parser = FileCreationNCBI(prog = 'Creates NBI Biosample and SRA spreadsheets',
        description = "NCBI Biosample and SRA spreadsheets for Candida auris submission.",
        epilog = "Example usage: python CA_post_mycosnp.py -qc <QC_STATS> -m <CAURIS_MASTER_LOG_COPY>"
        )
    parser.add_argument(
        "-qc",
        "--qc_stats",
        help="File containing QC stats in csv format."
    )
    parser.add_argument(
        "-m",
        "--metadata",
        help="Copy of Candida auris master log for metadata in tsv format."
    )
    parser.add_argument(
        "-r",
        "--run_name",
        type=str,
        help="Run name or batch of Candida auris in format CA_<machine>_YYMMDD.",
    )

    logging.debug("Run parser to call arguments downstream")
    args = parser.parse_args()

    logging.info("Going through ac stats")
    qc_stats_pass_fail = pass_fail(args.qc_stats)

    logging.info("Processing all files")
    meta_df, qc_df = create_dataframes(args.metadata, qc_stats_pass_fail)

    logging.info("Merging all data")
    merge_df = merge_dataframes(meta_df, qc_df)

    logging.info("Creating NCBI submission spreadsheets")
    create_ncbi_spreadsheets(merge_df, args.run_name)