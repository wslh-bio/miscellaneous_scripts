#!/usr/bin/env python3

# This script uses seqtk to subsample a fastq file down to a specific number of reads
# Usage: python3 subsample_with_seqtk.py [path to directory containing fastqs in gzip format] [path to seqtk] [target number of reads]

import sys
import os
import shlex
import glob
import argparse
import subprocess as sub

# Set up argparser and args
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s' % message)
        self.print_help()
        sys.exit(2)

parser = MyParser()
parser.add_argument("fastq_dir",help="Location of fastq files")
parser.add_argument("seqtk_dir",help="Location of seqtk executable")
parser.add_argument("num_reads",help="Number of reads to downsample to")

# get args
args = parser.parse_args()

# set fastq directory path and files
fastq_path = os.path.abspath(args.fastq_dir)
fastq_files = glob.glob(f"{fastq_path}/*.fastq.gz")

# set seqtk path
seqtk_path = os.path.abspath(args.seqtk_dir)

# set number of target reads
num_reads = args.num_reads

# run seqtk
print("Running seqtk...")
for fastq in fastq_files:
    subsample_file_path = fastq.split(".")[0]+"_subsample.fastq"
    outFile = open(subsample_file_path,"w")
    cmd = shlex.split(f"{seqtk_path}/seqtk sample -s100 {fastq} {num_reads}")
    sub.Popen(cmd, stdout=outFile).wait()
print("seqtk complete!")
