#!/usr/bin/env python

import sys
import logging
import argparse

import numpy as np

# from datetime import datetime

import pandas as pd

logging.basicConfig(level = logging.DEBUG, format = '%(levelname)s : %(message)s')

def sanitize_sample_name(dataframe):

    logging.debug("Sanitizing sample names")
    dataframe['WSLH Specimen Number'] = dataframe['WSLH Specimen Number'].str.split('_').str.get(0)

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

def create_dataframes(metadata, qc_stats, fks1_combined, clade_designation):

    logging.debug("Starting to create dataframes")
    meta_df     = pd.read_csv(metadata, sep='\t')
    qc_df       = pd.DataFrame(qc_stats)
    fks1_df     = pd.read_csv(fks1_combined, sep=',')
    clade_df    = pd.read_csv(clade_designation, sep=',')

    return meta_df, qc_df, fks1_df, clade_df

def merge_dfs(qc, metadata, fks1, clade):

    logging.debug("Clip 'Sample Name' and put into new column 'WSLH Specimen Number'")
    qc['WSLH Specimen Number'] = qc['Sample Name'].str.split('_').str[0].str.split('-').str[0].str.split('a').str[0]

    logging.debug("Create YYYY-MM for date of collection")
    metadata['collection_date'] = pd.to_datetime(metadata['Collection Date']).dt.strftime('%Y-%m')

    logging.debug("Renaming FKS1 sample column to ensure proper merge")
    fks1.rename(columns={"sample_id":"WSLH Specimen Number"}, inplace=True)

    logging.debug("Renaming Clade sample column to ensure proper merge")
    clade.rename(columns={'Sample':'WSLH Specimen Number'}, inplace=True)

    logging.debug("Sanitize sample names in dataframe before merge")
    clade = sanitize_sample_name(clade)
    fks1 = sanitize_sample_name(fks1)

    logging.debug("Create fastq file names")
    metadata['filename'] = metadata['HAI WGS ID']+'_R1_001.fastq.gz'
    metadata['filename2'] = metadata['HAI WGS ID']+'_R2_001.fastq.gz'

    logging.debug("Merge databases QC and Metadata")
    merged_df = pd.merge(qc, metadata, on='WSLH Specimen Number', how='inner')

    logging.debug("Merge databases Merged and FKS1")
    merged_df = pd.merge(merged_df, fks1, on='WSLH Specimen Number', how='left')

    logging.debug("Merge databases Merged and clade designation")
    merged_df = pd.merge(merged_df, clade, on='WSLH Specimen Number', how='left')

    return merged_df

def create_qc_reports(merged_df, run_name):

    logging.debug("Export total data")
    merged_df.to_csv(run_name +'_total_data.csv', index=False)

    logging.debug("pass.tsv for renaming files")
    df_passed = merged_df[merged_df['pass/fail'] == 'pass']
    df_passed.to_csv("pass.csv", columns=['WSLH Specimen Number', 'HAI WGS ID'], index=False)

    logging.debug("Drop duplicate columns to replace it with renamed columns")
    merged_df = merged_df.drop(columns=['Clade','fks1 mut'], axis=1)

    logging.debug("Rename Subtype_Closest_Match to fks1 mutation")
    merged_df = merged_df.rename(columns={'Subtype_Closest_Match':'Clade'})
    merged_df = merged_df.rename(columns={'mutation':'fks1 mut'})

    logging.debug("Setting detected or not detected based on if mutation is present")
    merged_df['fks1'] = np.where(merged_df['fks1 mut'] != "", 'DETECTED', merged_df['fks1'])
    merged_df['fks1'] = np.where(merged_df['fks1 mut'].isna(), 'NOT DETECTED', merged_df['fks1'])

    logging.debug("Sanitizing clade for readability")
    sanitize_clade(merged_df)

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
        'fks1 mut',
        'Comments'
    ]

    logging.debug("Creating qc_report file")
    merged_df.to_csv(run_name + '_qc_report.csv', columns=qc_report_columns, index=False)

def ncbi_spreadsheets(all_data, run_name):

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
    biosample_file = run_name+'_biosample.tsv'
    sra_file = run_name+'_sra.tsv'
    passed_samples = run_name+'_passed_total_data.tsv'

    logging.debug("Export csv files")
    df_biosample.to_csv(biosample_file, sep='\t', index=False)
    df_sra.to_csv(sra_file, sep='\t', index=False)

    logging.debug("Export passed total data")
    df_passed.to_csv(passed_samples, sep='\t', index=False)
    df_passed.to_csv("pass.csv", columns=['WSLH Specimen Number', 'HAI WGS ID'], index=False)

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
        help="Copy of Candida auris master log for metadata."
    )
    parser.add_argument(
        "-r",
        "--run_name",
        type=str,
        help="Run name or batch of Candida auris in format CA_<mbashachine>_YYMMDD.",
    )
    parser.add_argument(
        "-f",
        "--fks1_combined",
        help="FKS1 gene combined spreadsheet from Mycosnp-nf.",
    )
    parser.add_argument(
        "-c",
        "--clade_designation",
        help="Clade designation from mash_comparison.py script for Candida auris.",
    )

    logging.debug("Run parser to call arguments downstream")
    args = parser.parse_args()

    qc_stats_pass_fail = pass_fail(args.qc_stats)

    meta_df, qc_df, fks1_df, clade_df = create_dataframes(args.metadata, qc_stats_pass_fail, args.fks1_combined, args.clade_designation)

    merged_data = merge_dfs(qc_df, meta_df, fks1_df, clade_df)

    create_qc_reports(merged_data, args.run_name)

    ncbi_spreadsheets(merged_data, args.run_name)

