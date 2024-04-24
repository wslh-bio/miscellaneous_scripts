#!/usr/bin/env python3

import sys
import os
import shutil
import shlex
import argparse
import glob
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
import subprocess as sub
import pandas as pd
from pandas import DataFrame

class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s' % message)
        self.print_help()
        sys.exit(2)

parser = MyParser()
parser.add_argument("fasta_file",help="FASTA file containing sequences of interest")
parser.add_argument("mash_dir",help="Location of mash executable")
parser.add_argument("mash_db",help="Mash sketch database to compare FASTA files to")

args = parser.parse_args()

def fasta_to_fastas(fasta):
    fasta_files = []
    work_dir =  os.getcwd()
    with open(fasta, "r") as inFasta:
        for record in SeqIO.parse(inFasta, "fasta"):
            outFasta = record.id.replace(" ","_")+".fasta"
            outFasta_path = os.path.join(work_dir,outFasta)
            fasta_files.append(outFasta_path)
            SeqIO.write(record, outFasta_path, "fasta")
    return fasta_files

def run_mash_sketch(fasta,mash_path):
    sketch_file_path = fasta+".msh"
    cmd = shlex.split(f"{mash_path}/mash sketch {fasta}")
    sub.Popen(cmd).wait()
    return sketch_file_path

def run_mash_dist(fasta,mash_path,mash_db):
    dist_file_path = fasta.split(".")[0]+".dist"
    outFile = open(dist_file_path,"w")
    cmd = shlex.split(f"{mash_path}/mash dist -v 0.05 -d 0.1 {mash_db} {fasta}")
    sub.Popen(cmd, stdout=outFile).wait()
    cmd = shlex.split(f"sort -gk3 {dist_file_path}")
    sorted_dist_file_path = dist_file_path.replace(".dist",".sorted.dist")
    outFile = open(sorted_dist_file_path,"w")
    sub.Popen(cmd, stdout=outFile).wait()
    return sorted_dist_file_path

# function for summarizing Mash result files
def summarize_mash(file):
    # get sample id from file name
    sample_id = os.path.basename(file).split('.')[0].replace('.sorted.dist','')
    # read tsv file and add column names
    df = pd.read_csv(file, sep='\t', names=['RefSeq ID','Sample','Identity','P-value','Shared Hashes'])
    df = df.head(2)
    # keep only Sample RefSeq ID and Identity columns in data frame
    df = df[['Sample','RefSeq ID','Identity','P-value']]
    # check if data frame has two rows
    if len(df) == 0:
        # add two empty rows to species data frame
        df = df.append(pd.Series(), ignore_index=True)
        df = df.append(pd.Series(), ignore_index=True)
    if len(df) == 1:
        # add one empty row to species data frame
        df = df.append(pd.Series(), ignore_index=True)
    # if primary species is nan, replace with NA
    if str(df.iloc[0]['RefSeq ID']) == 'nan':
        primary_species = 'NA'
        primary_pval = 'NA'
    # else, get primary RefSeq ID match and put Identity in parentheses
    else:
        primary_species = df.iloc[0]['RefSeq ID'] + ' (' + str(df.iloc[0]['Identity']) + ')'
        primary_pval = str(df.iloc[0]['P-value'])
    # repeat for secondary species
    if str(df.iloc[1]['RefSeq ID']) == 'nan':
        secondary_species = 'NA'
        secondary_pval = 'NA'
    else:
        print(df.iloc[1]['RefSeq ID'])
        secondary_species = df.iloc[1]['RefSeq ID'] + ' (' + str(df.iloc[1]['Identity']) + ')'
        secondary_pval = str(df.iloc[1]['P-value'])
    pvals = primary_pval + ";" + secondary_pval
    # list of lists
    combined = [[sample_id, primary_species, secondary_species,pvals]]
    # convert list of lists to data frame
    combined_df = DataFrame(combined, columns=['Sample','Primary Mash Species (Identity)','Secondary Mash Species (Identity)','Mash P-Value (Primary Species;Seconday Species)'])
    return combined_df

def cleanup_dirs(dir_name,extension):
    work_dir =  os.getcwd()
    new_dir = os.path.join(work_dir,dir_name)
    if os.path.exists(new_dir):
        files = glob.glob(f"*.{extension}")
        for file in files:
            shutil.copy(file,os.path.join(new_dir,file))
            os.remove(file)
    else:
        os.mkdir(new_dir)
        files = glob.glob(f"*.{extension}")
        for file in files:
            shutil.copy(file,os.path.join(new_dir,file))
            os.remove(file)
    return(files)

fasta_file = args.fasta_file
print("Parsing fasta file...")
fasta_files = fasta_to_fastas(fasta_file)
fasta_files = list(fasta_files)
#print(fasta_files)
print("Parsing complete!")

mash_path = os.path.abspath(args.mash_dir)
mash_paths = [mash_path] * len(fasta_files)
print("Running mash sketch...")
sketches = map(run_mash_sketch,fasta_files,mash_paths)
print("Mash sketch complete!")
sketches = list(sketches)
#print(sketches)


sketch_db_path = args.mash_db
sketch_db_paths = [sketch_db_path] * len(sketches)
mash_paths = [mash_path] * len(sketches)
print("Running Mash dist...")
sorted_dists = map(run_mash_dist,sketches,mash_paths,sketch_db_paths)
print("Mash dist complete!")
sorted_dists = list(sorted_dists)
#print(sorted_dists)

# summarize dist files
print("Summarizing results...")
results = map(summarize_mash, sorted_dists)

# concatenate summary results and write to tsv
mash_results = list(results)
#print(mash_results)

if len(mash_results) > 1:
    data_concat = pd.concat(mash_results)
    data_concat.to_csv(f'mash_results.tsv',sep='\t', index=False, header=True, na_rep='NaN')
else:
    mash_results = mash_results[0]
    results.to_csv(f'mash_results.tsv',sep='\t', index=False, header=True, na_rep='NaN')
print("Summary complete!")

print("Cleaning up intermediate files...")
dirs = ["fastas","sketches","sorted_dists","dists"]
file_extensions = ["fasta","fasta.msh","sorted.dist","dist"]
new_dirs = map(cleanup_dirs,dirs,file_extensions)
print(list(new_dirs))
print("Cleaning complete!")
print("Script concluded")
