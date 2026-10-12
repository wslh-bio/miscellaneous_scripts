# NCBI Genome Header Builder

`NCBI-Genome-Header-Builder.py` converts FASTA headers from a Unicycler
assembly into NCBI-style definition lines for chromosomes, plasmids, and
unplaced contigs.

The script does not require third-party Python packages. Python 3.10 or newer
is recommended.

## Usage

Run the script with the input FASTA file and the sample ID:

```bash
python NCBI/NCBI-Genome-Header-Builder.py \
  assembly.fasta \
  --sample-id 2022GN-00355
```

By default, the output is written beside the input file using the sample ID:

```text
2022GN-00355.ncbi.fasta
```

Use `--output-dir` to write the generated file to another directory:

```bash
python NCBI/NCBI-Genome-Header-Builder.py \
  22MP019071.fasta \
  --sample-id 2022GN-00355 \
  --output-dir /path/to/NCBI-Genbank
```

The output will be:

```text
/path/to/NCBI-Genbank/2022GN-00355.ncbi.fasta
```

Use `--output` to choose an exact output path when processing one input file:

```bash
python NCBI/NCBI-Genome-Header-Builder.py \
  assembly.fasta \
  --sample-id 2022GN-00355 \
  --output 2022GN-00355.fasta
```

Multiple input files can be supplied when they all belong to the same sample.
The same `--sample-id` is applied to every input file, and the default output
name is based on that sample ID. Processing multiple files with the same
sample ID will therefore overwrite the same output file. For different
samples, run the command once per sample.

## Example

Given this input:

```text
>1 length=5487804 depth=1.00x circular=true
ACGT
>2 length=142690 depth=7.40x circular=true
TGCA
>5 length=16824 depth=1.51x
AAAA
```

Running:

```bash
python NCBI/NCBI-Genome-Header-Builder.py \
  assembly.fasta \
  --sample-id 2022GN-00355
```

produces:

```text
>2022GN-00355 [location=chromosome] [topology=circular] [completeness=complete]
ACGT
>p2022GN-00355_2 [plasmid-name=p2022GN-00355_2] [topology=circular] [completeness=complete]
TGCA
>2022GN-00355_contig_5
AAAA
```

## Classification logic

The value supplied with `--sample-id` is the source of truth for output
filenames and normalized chromosome/plasmid names. The input filename does not
determine the sample ID.

### Chromosomes

- A record whose ID exactly matches `--sample-id` is the chromosome.
- A numeric record ID of `1` is the chromosome when an exact sample-ID record
  is not present.
- If neither is present, the first non-plasmid, non-numeric record is used as
  the chromosome for compatibility with older input naming.
- The chromosome is renamed to `--sample-id`.
- `circular=true` adds:
  `[topology=circular] [completeness=complete]`.
- Without `circular=true`, only `[location=chromosome]` is added.

### Plasmids

- Existing IDs matching `p<anything>_<number>` are normalized to
  `p<sample-id>_<number>`.
- Numeric IDs greater than `1` are treated as plasmids only when the input
  header contains `circular=true`.
- Circular non-numeric records that are not the chromosome are treated as
  plasmids and renamed to `p<sample-id>_<original-id>`.
- Plasmids receive a `[plasmid-name=...]` tag.
- Circular plasmids also receive:
  `[topology=circular] [completeness=complete]`.
- A plasmid without `circular=true` receives no circular or complete tags.

### Unplaced contigs

- Numeric IDs greater than `1` without `circular=true` are treated as
  contigs whose chromosomal placement is unknown.
- They are renamed to `<sample-id>_contig_<number>` and receive no `location`
  modifier because `location=unplaced` is not a valid NCBI value.
- Other records that cannot be classified as the chromosome or a plasmid are
  also emitted without a `location` modifier.
- Do not use `location=extrachromosomal` unless the sequence is known to be
  extrachromosomal. An uncertain contig should not be labeled
  `extrachromosomal`.

## Input assumptions

This script is designed for FASTA output from **Unicycler**. It assumes:

- The assembly uses numeric record IDs such as `1`, `2`, and `5`, or
  Unicycler-style plasmid IDs such as `pSAMPLE_2`.
- Header metadata uses whitespace-separated `key=value` fields.
- `circular=true` is present only for sequences that have been circularized.
- Numeric assembly ID `1` represents the largest sequence and is the
  chromosome.
- Numeric assemblies greater than `1` can be called plasmids only when they
  explicitly contain `circular=true`.
- Non-circular assemblies cannot be assigned to a chromosome or plasmid based
  on size or numeric ID alone.
- Contigs with unknown chromosomal placement are emitted without a
  `location` modifier because NCBI does not accept `location=unplaced`.

The script may not work correctly with FASTA output from other assemblers.
Other assemblers may use different record naming, metadata, circularity
indicators, or contig ordering. Review the generated FASTA headers before
submitting them to NCBI.

## Validation and errors

The script rejects:

- Duplicate input record IDs
- FASTA sequence data before the first header
- Headers without record IDs
- Records without sequence data
- Empty FASTA files
- An output path that is the same as the input path

Input sequence lines are preserved, while original header metadata is replaced
with the normalized NCBI tags.
