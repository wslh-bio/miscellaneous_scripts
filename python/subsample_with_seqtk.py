#!/usr/bin/env python3

# This script uses seqtk to downsample a fastq file to a specific number of num_reads
# Usage: python3 run_seqtk.py [path to directory containing fastqs in gzip format] \\
# [path to seqtk] [output path] [target number of reads]

import sys
import os
import shlex
import glob
import shutil
import argparse
import subprocess as sub

# Set up parser
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write("error: %s" % message)
        self.print_help()
        sys.exit(2)

parser = MyParser()
parser.add_argument("fastq_dir",help="Location of fastq files")
parser.add_argument("seqtk_dir",help="Location of seqtk executable")
parser.add_argument("output_dir",help="Output directory")
parser.add_argument("num_reads",help="Number of reads to downsample to")

args = parser.parse_args()

# get fastq directory path and files
fastq_path = os.path.abspath(args.fastq_dir)
fastq_files = glob.glob(f"{fastq_path}/*.fastq.gz")

# get seqtk path
seqtk_path = os.path.abspath(args.seqtk_dir)

# get output path
output_path = os.path.abspath(args.output_dir)

# get number of target reads
num_reads = args.num_reads

# run seqtk
print("Running seqtk...")
for fastq in fastq_files:
    subsample_file = os.path.basename(fastq).replace(".fastq.gz","_subsample.fastq")
    subsample_file_path = os.path.join(output_path,subsample_file)
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    outFile = open(subsample_file_path,"w")
    cmd = shlex.split(f"{seqtk_path}/seqtk sample -s100 {fastq} {num_reads}")
    sub.Popen(cmd, stdout=outFile).wait()
print("seqtk complete!")
