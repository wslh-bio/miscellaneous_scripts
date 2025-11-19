#!/usr/bin/env python3

import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--fasta', type = str, required=True)
parser.add_argument('--position', type = int, required = True)
args = parser.parse_args()

fasta = args.fasta
rotate_pos = args.position - 1

seq = ''
header = ''
handle = fasta.split(".")[0]
output_name = f"{handle}.rotated.fasta"

with open(fasta,"r") as fastaFile:
    for line in fastaFile:
        line = line.strip()
        if line == '':
            continue
        if line[0] == '>':
            header = line
        else:
            seq += line

left = seq[:rotate_pos]
right = seq[rotate_pos:]

rotated_fasta = right+left

with open(output_name,"w") as outFile:
 outFile.write(f"{header}\n{rotated_fasta}")
