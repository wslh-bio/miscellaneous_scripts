#!/usr/bin/env python

import sys
import argparse
import os

from fastq_dir_to_samplesheet import fastq_dir_to_samplesheet


# Parse Arguments
def parse_args(args=None):
    """Parse args function"""
    description = ("This script uses the fastq_dir_to_samplesheet.py in spriggan/bin and generates a new spriggan samplesheet that replaces "
                   "the local path of the fastq files in the spriggan samplesheet with the s3 URI where the files live on AWS. The script "
                   "assumes the directory containing the fastq files is named the same as the run ID."
                   )
    epilog = (
        "Example usage: make_and_update_spriggan_samplesheet.py [args...]"
    )
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument(
        "-f",
        "--FASTQ_DIR",
        type=str,
        dest="FQ_DIR",
        default="",
        help="Path to fastq files directory.",
    )
    parser.add_argument(
        "-r",
        "--run_id",
        type=str,
        dest="RUNID",
        default="",
        help="AR Run ID",
    )
    parser.add_argument(
        "-s",
        "--samplesheet",
        type=str,
        dest="SAMPLESHEET",
        default="",
        help="Final name of samplesheet.",
    )
    return parser.parse_args(args)


def make_and_update_samplesheet(fq_dir, run_id, final_samplesheet):
    raw_samplesheet = run_id + "_raw_samplesheet.csv"
    fastq_dir_to_samplesheet(fq_dir, raw_samplesheet)
    s3_uri = "s3://prod-wslh-sequencing-inbox/spriggan/" # hard-coded for WSLH Spriggan/AR workflow on NF Tower PROD env
    with open(raw_samplesheet, 'r') as rs, open(final_samplesheet, "w") as fs:
        for line in rs:
            if line.startswith("sample"):
                fs.write(line)
            else:
                sample = line.split(",")[0]
                fq1 = line.split(",")[1]
                # append the S3 URI to the path
                new_fq1 = s3_uri + fq1
                fq2 = line.split(",")[-1]
                new_fq2 = s3_uri + fq2
                fs.write(sample + "," + new_fq1 + "," + new_fq2)
    if final_samplesheet:
        os.remove(raw_samplesheet)



def main(args=None):
    args = parse_args(args)
    make_and_update_samplesheet(fq_dir=args.FQ_DIR, run_id=args.RUNID, final_samplesheet=args.SAMPLESHEET)

if __name__ == "__main__":
    sys.exit(main())
