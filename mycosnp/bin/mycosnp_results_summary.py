#!/usr/bin/env python

import sys
import logging
import argparse

import numpy as np
import pandas as pd

logging.basicConfig(level = logging.DEBUG, format = '%(levelname)s : %(message)s')

def sanitize_sample_name(dataframe):

    logging.debug("Sanitizing sample names")
    dataframe['Sample Name'] = dataframe['Sample Name'].str.split('_').str.get(0)

    return dataframe

def sanitize_clade(dataframe):

    logging.debug("Setting up clade names in dictionary")
    clade_dict = {'cladeI-':'Clade I',
                  'cladeII-':'Clade II',
                  'cladeIII-':'Clade III',
                  'cladeIV-':'Clade IV',
                  'cladeV-':'Clade V',
                  'cladeVI-':'Clade VI'}

    logging.debug("Replacing clade names based on dictionary")
    for key, value in clade_dict.items():
        dataframe.loc[dataframe['Clade'].str.contains(key, case=False, na=False), 'Clade'] = value

    return dataframe

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

def create_dataframes(qc_stats, fks1_combined, clade_designation):

    logging.debug("Starting to create dataframes")
    qc_df       = pd.DataFrame(qc_stats)
    fks1_df     = pd.read_csv(fks1_combined, sep=',')
    clade_df    = pd.read_csv(clade_designation, sep=',')

    return qc_df, fks1_df, clade_df

def merge_dfs(qc, fks1, clade):

    logging.debug("Clip 'Sample Name' and put into new column 'WSLH Specimen Number'")
    qc['WSLH Specimen Number'] = qc['Sample Name'].str.split('_').str[0].str.split('-').str[0].str.split('a').str[0]

    logging.debug("Renaming FKS1 columns to ensure proper merge")
    fks1.rename(columns={"sample_id":"Sample Name"}, inplace=True)
    fks1.rename(columns={'mutation':'fks1 mut'}, inplace=True)

    logging.debug("Renaming Clade columns to ensure proper merge")
    clade.rename(columns={'Sample':'Sample Name'}, inplace=True)
    clade.rename(columns={'Subtype_Closest_Match':'Clade'}, inplace=True)

    logging.debug("Sanitize sample names in dataframe before merge")
    clade = sanitize_sample_name(clade)
    fks1 = sanitize_sample_name(fks1)

    logging.debug("Merge databases QC and FKS1")
    fks1 = fks1.groupby('Sample Name').agg({
        'fks1 mut': lambda x: ', '.join(x.dropna().unique())
    }).reset_index()

    merged_df = pd.merge(qc, fks1, on='Sample Name', how='left')

    logging.debug("Merge databases Merged and clade designation")
    merged_df = pd.merge(merged_df, clade, on='Sample Name', how='left')

    return merged_df

def create_qc_reports(merged_df, run_name):

    merged_df['fks1'] = np.nan

    logging.debug("Setting detected or not detected based on if mutation is present")
    merged_df['fks1'] = np.where(merged_df['fks1 mut'] != "", 'DETECTED', merged_df['fks1'])
    merged_df['fks1'] = np.where(merged_df['fks1 mut'].isna(), 'NOT DETECTED', merged_df['fks1'])

    logging.debug("Sanitizing clade for readability")
    merged_df = sanitize_clade(merged_df)

    logging.debug("Setting up columns for qc_report")
    qc_report_columns=[
        'Sample Name',
        'Reads Before Trimming',
        'GC Before Trimming',
        'Average Q Score Before Trimming',
        'Reference Length Coverage Before Trimming',
        'Reads After Trimming',
        'Paired Reads After Trimming',
        'Unpaired Reads After Trimming',
        'GC After Trimming',
        'Average Q Score After Trimming',
        'Reference Length Coverage After Trimming',
        'Mean Coverage Depth',
        'Reads Mapped',
        'Genome Fraction at 10X',
        'pass/fail',
        'Clade',
        'fks1',
        'fks1 mut'
    ]

    logging.debug("Creating qc_report file")
    merged_df.to_csv(run_name + '_qc_report.csv', columns=qc_report_columns, index=False)

class CompileResults(argparse.ArgumentParser):

    def error(self, message):
        self.print_help()
        sys.stderr.write(f'\nERROR DETECTED: {message}\n')

        sys.exit(1)

if __name__ == "__main__":

    parser = CompileResults(prog = 'Compiles all of the mycosnp results into a WSLH specific report',
        description = "Generate QC report and NCBI Biosample and SRA spreadsheets for Candida auris submission.",
        epilog = "Example usage: python CA_post_mycosnp.py -qc <QC_STATS> -m <CAURIS_MASTER_LOG_COPY> -r <BATCH_NAME> -f <FKS1> -c <CLADE_DESIGNATION>"
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
    parser.add_argument(
        "-f",
        "--fks1_combined",
        help="FKS1 gene combined spreadsheet from Mycosnp-nf in csv format.",
    )
    parser.add_argument(
        "-c",
        "--clade_designation",
        help="Clade designation from sourmash in csv format, from Pre-mycosnp-nf.",
    )

    logging.debug("Run parser to call arguments downstream")
    args = parser.parse_args()

    logging.info("Going through ac stats")
    qc_stats_pass_fail = pass_fail(args.qc_stats)

    logging.info("Processing all files")
    qc_df, fks1_df, clade_df = create_dataframes(qc_stats_pass_fail, args.fks1_combined, args.clade_designation)

    logging.info("Merging all data")
    merged_data = merge_dfs(qc_df, fks1_df, clade_df)

    logging.info("Creating QC reports")
    create_qc_reports(merged_data, args.run_name)

