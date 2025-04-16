#!/usr/bin/env python
import pandas as pd
import os
import sys
import glob
import argparse
from datetime import datetime


def parse_args(args=None):
    Description = (
        "Generate QC report and NCBI Biosample and SRA spreadsheets for Candida auris submission."
    )
    Epilog = "Example usage: python CA_post_mycosnp.py -qc <QC_STATS> -m <CAURIS_MASTER_LOG_COPY> -r <BATCH_NAME>"

    parser = argparse.ArgumentParser(description=Description, epilog=Epilog)
    parser.add_argument(
        "-qc",
        "--qc_stats",
        dest="QC_STATS", 
        help="File containing QC stats in csv format."
    )
    parser.add_argument(
        "-m",
        "--metadata",
        dest="METADATA",
        help="Copy of Candida auris master log for metadata."
    )
    parser.add_argument(
        "-r",
        "--run_name",
        type=str,
        dest="RUN_NAME",
        help="Run name or batch of Candida auris in format CA_<machine>_YYMMDD.",
    )
    parser.add_argument(
        "-f",
        "--fks_combined",
        dest="FKS_COMBINED",
        help="FKS1 gene combined spreadsheet from Mycosnp-nf.",
    )
    parser.add_argument(
        "-c",
        "--clade_designation",
        dest="CLADE",
        help="Clade designation from mash_comparison.py script for Candida auris.",
    )
    return parser.parse_args(args)


def pass_fail (qc_stats):
    # Read csv files
    qc = pd.read_csv(qc_stats, sep= '\t')

    # remove "%" from "GC content after trimming"
    qc['GC After Trimming normalized'] = qc['GC After Trimming'].str.rstrip('%').astype(float)

    # Define pass fail criteria
    pass_fail_criteria = (
        (qc['GC After Trimming normalized'] >= 42) &
        (qc['GC After Trimming normalized'] <= 47.5) &
        (qc['Average Q Score After Trimming'] >= 28) &
        (qc['Mean Coverage Depth'] >= 20))
    
    qc.loc[(pass_fail_criteria), 'pass/fail'] = 'pass'
    qc.loc[(~pass_fail_criteria), 'pass/fail'] = 'fail'
    
    #qc.to_csv('test.csv', index=False)
    return qc


def merge(qc_stats, metadata, run_name):
    # Read csv files
    qc = pd.DataFrame(qc_stats)
    meta = pd.read_csv(metadata, sep='\t')

    # Clip "Sample Name" and put into new column 'WSLH Specimen Number'
    qc['WSLH Specimen Number'] = qc['Sample Name'].str.split('_').str[0].str.split('-').str[0].str.split('a').str[0]

    # Create YYYY-MM for date of collection
    meta['collection_date'] = pd.to_datetime(meta['Collection Date']).dt.strftime('%Y-%m')

    # Create fastq file names
    meta['filename'] = meta['HAI WGS ID']+'_R1_001.fastq.gz'
    meta['filename2'] = meta['HAI WGS ID']+'_R2_001.fastq.gz'

    # Merge databases
    merged_df = pd.merge(qc, meta, on='WSLH Specimen Number', how='inner')

    # Export total data
    merged_df.to_csv(run_name+'_total_data.csv', index=False)

    # Create pass.tsv for renameing files
    df_passed = merged_df[merged_df['pass/fail'] == 'pass']
    df_passed.to_csv("pass.csv", columns=['WSLH Specimen Number', 'HAI WGS ID'], index=False)

    # Create qc_report
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
    merged_df.to_csv(run_name+'_qc_report.csv', columns=qc_report_columns, index=False)
 

    return merged_df

#def qc_report_creation(prelim_qc_report, fks1, clade_designation)

def ncbi_spreadsheets(all_data, run_name):

    df = pd.DataFrame(all_data)
    df_passed = df[df['pass/fail'] == 'pass']

    # Create a dictionary with column names and corresponding biosample attributes for Biosample
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

    # Create a dictionary with column names and corresponding data for SRA
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

    # Create DataFrame from the dictionary
    df_biosample = pd.DataFrame(biosample)
    df_sra = pd.DataFrame(sra)

    # Name files
    biosample_file = run_name+'_biosample.tsv'
    sra_file = run_name+'_sra.tsv'
    passed_samples = run_name+'_passed_total_data.tsv'

    # Export csv files
    df_biosample.to_csv(biosample_file, sep='\t', index=False)
    df_sra.to_csv(sra_file, sep='\t', index=False)

    # Export passed total data
    df_passed.to_csv(passed_samples, sep='\t', index=False)
    df_passed.to_csv("pass.csv", columns=['WSLH Specimen Number', 'HAI WGS ID'], index=False)

def main(args=None):
    args = parse_args(args)
    qc_stats_pass_fail = pass_fail(
        qc_stats=args.QC_STATS
    )
    merged_data = merge(
        qc_stats= qc_stats_pass_fail,
        metadata=args.METADATA,
        #fks_combined=args.FKS_COMBINED,
        #clade_designation=args.CLADE,
        run_name=args.RUN_NAME,
    )
    ncbi_spreadsheets(all_data=merged_data,
              run_name=args.RUN_NAME,
    )


if __name__ == "__main__":
    sys.exit(main())
