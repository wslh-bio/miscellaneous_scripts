#!/usr/bin/env python

import os
import argparse
import sys
import pandas as pd


# Parse Arguments
def parse_args(args=None):
    """Parse args function"""
    description = ("The fastq files of samples that were run through the Spriggan workflow and passed "
                   "sequencing QC need to be uploaded to NCBI with a specific naming convention. This script renames "
                   "the fastq files by replacing the WSLH Specimen ID with the HAI WGS ID and keeps only the read pair "
                   "number. This program requires the final spriggan QC report containing both the WLSH Specimen "
                   "ID and HAI WGS ID. This script also generates the 'pass.tsv' file needed for upload to NCBI. "
                   "The fastq files for the samples that passed QC must exist in the input directory provided."
                   )
    epilog = (
        "Example usage: python rename_AR_fqs.py [args...]"
    )
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument(
        "-f",
        "--fq_dir",
        type=str,
        dest="FQDIR",
        default="",
        help="Path to the fastq files.",
    )
    parser.add_argument(
        "-s",
        "--spriggan_report",
        type=str,
        dest="SPRIGGAN_REPORT",
        default="",
        help="Path to the spriggan report.",
    )
    return parser.parse_args(args)


def rename_fq(spriggan_report, directory):
    # replace the WSLH Specimen ID in the name of the fastq files with the HAI WGS ID, keeping only the read pair
    sample_dict = {}
    df = pd.read_excel(io=spriggan_report, sheet_name="passed")  # Read excel sheet and only use the samples that passed QC
    pass_df = df.to_csv("pass.tsv", columns=['WSLH Specimen Number', 'HAI WGS ID'], sep='\t', index=False)  # create the pass.tsv file
    with open("pass.tsv", 'r') as pf:  # use the pass.tsv file to create the WSLH-HAI ID association
        for line in pf:
            if not line.startswith("WSLH Specimen Number"):
                sample_dict[line.rstrip().split("\t")[0]] = line.rstrip().split("\t")[-1]
    for root, dirs, files in os.walk(directory):
        for name in files:
            # read_pair = name.split("-")[3].split("_")[3]
            read_pair = name.split("_")[3]
            wslh_id = name.split("-")[0]
            shortened = wslh_id + "_" + read_pair + ".fastq.gz"

            # list comprehension to use the dictionary and put the WSLH ID-HAI WGS ID match-and-swap into a list
            hai_id = [hai for wslh, hai in sample_dict.items() if shortened.split("_")[0] in wslh]
            for item in hai_id:
                new_fq = item + "_" + shortened.split("_")[-1]
                try:
                    os.rename(os.path.join(root, name), os.path.join(root, new_fq))
                    print(f"Successfully renamed {name} to: {new_fq} \n")
                except Exception as e:
                    print(e)
                    print(f"Failed to rename {name} to: {new_fq} \n")


def main(args=None):
    args = parse_args(args)
    rename_fq(spriggan_report=args.SPRIGGAN_REPORT, directory=args.FQDIR)


if __name__ == "__main__":
    sys.exit(main())