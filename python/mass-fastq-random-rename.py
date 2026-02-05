#!/usr/bin/env python3

import os
import re
import random
import string
import argparse
from collections import defaultdict

def random_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def find_pairs(files):
    """
    Groups FASTQ files into R1/R2 pairs.
    """
    pairs = defaultdict(dict)

    pattern = re.compile(r'(.*?)(?:_R?)([12])(?:_\d+)?(\.f(ast)?q(\.gz)?)$', re.IGNORECASE)

    for f in files:
        match = pattern.match(f)
        if not match:
            continue

        sample_base = match.group(1)
        read_num = match.group(2)

        pairs[sample_base][read_num] = f

    return {k: v for k, v in pairs.items() if '1' in v and '2' in v}

def main(input_dir, output_dir, map_file):
    os.makedirs(output_dir, exist_ok=True)

    files = [f for f in os.listdir(input_dir) if f.endswith(('.fastq', '.fastq.gz', '.fq', '.fq.gz'))]
    pairs = find_pairs(files)

    with open(map_file, 'w') as mf:
        mf.write("random_id,original_R1,original_R2\n")

        for _, pair in pairs.items():
            rid = random_id()

            r1 = pair['1']
            r2 = pair['2']

            ext = re.search(r'(\.f(ast)?q(\.gz)?)$', r1, re.IGNORECASE).group(1)

            new_r1 = f"{rid}_R1{ext}"
            new_r2 = f"{rid}_R2{ext}"

            os.rename(
                os.path.join(input_dir, r1),
                os.path.join(output_dir, new_r1)
            )
            os.rename(
                os.path.join(input_dir, r2),
                os.path.join(output_dir, new_r2)
            )

            mf.write(f"{rid},{r1},{r2}\n")

    print(f"Renamed {len(pairs)} paired samples.")
    print(f"Mapping file written to {map_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Randomly rename paired-end FASTQ files")
    parser.add_argument("-i", "--input-dir", required=True, help="Directory with FASTQ files")
    parser.add_argument("-o", "--output-dir", required=True, help="Directory for renamed FASTQs")
    parser.add_argument("-m", "--map-file", default="fastq_rename_map.csv",
                        help="CSV mapping file (default: fastq_rename_map.csv)")

    args = parser.parse_args()
    main(args.input_dir, args.output_dir, args.map_file)
