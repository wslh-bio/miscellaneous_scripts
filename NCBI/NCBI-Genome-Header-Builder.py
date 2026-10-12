#!/usr/bin/env python3
"""Build NCBI genome submission deflines for circular bacterial replicons."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator


LOGGER = logging.getLogger(__name__)
PLASMID_ID = re.compile(r"^p(?P<sample>.+)_(?P<number>\d+)$")
NUMERIC_PLASMID_ID = re.compile(r"^(?P<number>\d+)$")
HEADER_ATTRIBUTE = re.compile(r"(?P<key>[A-Za-z][A-Za-z0-9_-]*)=(?P<value>[^\s]+)")


class FastaFormatError(ValueError):
    """Raised when an input FASTA file cannot be processed safely."""


def output_path(
    input_path: Path, output_directory: Path | None, sample_id: str
) -> Path:
    """Return the output path for an input FASTA file."""
    destination = output_directory or input_path.parent
    return destination / f"{sample_id}.ncbi.fasta"


def classify_record(
    record_id: str,
    sample_id: str,
    chromosome_id: str,
    attributes: dict[str, str],
) -> tuple[str, str]:
    """Return the NCBI assignment and normalized name for a record ID."""
    if record_id == chromosome_id:
        return "chromosome", sample_id

    match = PLASMID_ID.fullmatch(record_id)
    if match:
        return "plasmid", f"p{sample_id}_{match.group('number')}"

    match = NUMERIC_PLASMID_ID.fullmatch(record_id)
    if match:
        if match.group("number") == "1":
            return "chromosome", sample_id
        if attributes.get("circular", "").lower() == "true":
            return "plasmid", f"p{sample_id}_{match.group('number')}"
        return "unplaced", f"{sample_id}_contig_{match.group('number')}"

    if attributes.get("circular", "").lower() == "true":
        return "plasmid", f"p{sample_id}_{record_id}"

    return "unplaced", record_id


def ncbi_header(
    record_id: str,
    sample_id: str,
    chromosome_id: str,
    attributes: dict[str, str],
) -> str:
    """Create an NCBI-compatible defline using explicit source metadata."""
    assignment, name = classify_record(
        record_id, sample_id, chromosome_id, attributes
    )
    if assignment == "chromosome":
        tags = "[location=chromosome]"
    elif assignment == "plasmid":
        tags = f"[plasmid-name={name}]"
    else:
        tags = ""
    if attributes.get("circular", "").lower() == "true":
        tags += " [topology=circular] [completeness=complete]"
    return f">{name}{f' {tags}' if tags else ''}"


def records(
    lines: Iterable[str],
) -> Iterator[tuple[str, dict[str, str], list[str]]]:
    """Yield FASTA record IDs, source attributes, and sequence lines."""
    record_id: str | None = None
    attributes: dict[str, str] = {}
    sequence: list[str] = []

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue
        if line.startswith(">"):
            if record_id is not None:
                yield record_id, attributes, sequence
            header = line[1:]
            record_id = header.split(maxsplit=1)[0]
            if not record_id:
                raise FastaFormatError(f"line {line_number}: FASTA header has no ID")
            attributes = {
                match.group("key").lower(): match.group("value")
                for match in HEADER_ATTRIBUTE.finditer(header)
            }
            sequence = []
        else:
            if record_id is None:
                raise FastaFormatError(
                    f"line {line_number}: sequence found before the first FASTA header"
                )
            sequence.append(line.strip())

    if record_id is not None:
        yield record_id, attributes, sequence


def build_headers(input_path: Path, output_path: Path, sample_id: str) -> int:
    """Convert one FASTA file and return the number of records written."""
    seen_ids: set[str] = set()
    count = 0

    with input_path.open("r", encoding="utf-8") as input_file:
        parsed_records = list(records(input_file))

    exact_chromosome = next(
        (record_id for record_id, _, _ in parsed_records if record_id == sample_id),
        None,
    )
    numeric_chromosome = next(
        (record_id for record_id, _, _ in parsed_records if record_id == "1"),
        None,
    )
    chromosome_id = exact_chromosome or numeric_chromosome or next(
        (
            record_id
            for record_id, _, _ in parsed_records
            if not (
                PLASMID_ID.fullmatch(record_id)
                or NUMERIC_PLASMID_ID.fullmatch(record_id)
            )
        ),
        None,
    )

    with output_path.open("w", encoding="utf-8", newline="\n") as output_file:
        for record_id, attributes, sequence in parsed_records:
            if record_id in seen_ids:
                raise FastaFormatError(f"duplicate FASTA record ID: '{record_id}'")
            seen_ids.add(record_id)
            if not sequence:
                raise FastaFormatError(f"record '{record_id}' has no sequence")
            if chromosome_id is None:
                normalized_header = ncbi_header(
                    record_id, sample_id, "", attributes
                )
            else:
                normalized_header = ncbi_header(
                    record_id, sample_id, chromosome_id, attributes
                )
            output_file.write(f"{normalized_header}\n")
            output_file.write("\n".join(sequence))
            output_file.write("\n")
            count += 1

    if count == 0:
        raise FastaFormatError("input contains no FASTA records")
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add NCBI chromosome/plasmid/unplaced assignment and "
            "circular-complete tags to bacterial FASTA headers."
        ),
        epilog=(
            "Example: %(prog)s assembly.fasta --sample-id 25MP010801 "
            "--output-dir ncbi_headers"
        ),
    )
    parser.add_argument(
        "fasta",
        type=Path,
        nargs="+",
        help="FASTA file(s) to process",
    )
    parser.add_argument(
        "--sample-id",
        required=True,
        help="sample ID used to identify the chromosome and plasmids",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output file; valid only when processing one input file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="directory for generated <sample-id>.ncbi.fasta files",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    if args.output and len(args.fasta) != 1:
        LOGGER.error("--output can only be used with one input file")
        return 2
    if args.output and args.output_dir:
        LOGGER.error("--output and --output-dir cannot be used together")
        return 2

    try:
        for input_path in args.fasta:
            destination = args.output or output_path(
                input_path, args.output_dir, args.sample_id
            )
            if input_path.resolve() == destination.resolve():
                raise ValueError(
                    f"{input_path}: output must differ from the input file"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            count = build_headers(input_path, destination, args.sample_id)
            LOGGER.info("Wrote %d records to %s", count, destination)
    except (OSError, ValueError, FastaFormatError) as error:
        LOGGER.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())