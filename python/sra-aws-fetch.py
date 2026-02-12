#!/usr/bin/env python3

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path


SRA_BUCKET_PREFIX = "s3://sra-pub-run-odp/sra"


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Download SRA files from AWS and extract paired FASTQ files named "
			"using sample names from a CSV file."
		)
	)
	parser.add_argument("csv", help="Path to CSV file")
	parser.add_argument(
		"--accession-column",
		default='acc',
		help="CSV column name containing SRA accession (e.g., SRR12345678)",
	)
	parser.add_argument(
		"--sample-column",
		default='sample_name',
		help="CSV column name containing sample names",
	)
	parser.add_argument(
		"--out-dir",
		default="fastq_out",
		help="Output directory for renamed FASTQ files (default: fastq_out)",
	)
	parser.add_argument(
		"--work-dir",
		default="sra_work",
		help=(
			"Working directory for downloaded .sra files and temporary fasterq-dump "
			"outputs (default: sra_work)"
		),
	)
	parser.add_argument(
		"--skip-existing",
		action="store_true",
		help="Skip sample if output FASTQ files already exist",
	)
	return parser.parse_args()


def run_command(command: list[str], stream_output: bool = False) -> None:
	if stream_output:
		process = subprocess.run(command)
		if process.returncode != 0:
			cmd_str = " ".join(command)
			raise RuntimeError(f"Command failed: {cmd_str}")
		return

	process = subprocess.run(command, capture_output=True, text=True)
	if process.returncode != 0:
		cmd_str = " ".join(command)
		raise RuntimeError(
			f"Command failed: {cmd_str}\n"
			f"stdout:\n{process.stdout}\n"
			f"stderr:\n{process.stderr}"
		)


def sanitize_filename(name: str) -> str:
	sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
	sanitized = sanitized.strip("._-")
	return sanitized or "sample"


def ensure_tools_available() -> None:
	missing = []
	for tool in ("aws", "fasterq-dump"):
		if shutil.which(tool) is None:
			missing.append(tool)
	if missing:
		joined = ", ".join(missing)
		raise RuntimeError(
			f"Required tool(s) not found in PATH: {joined}. "
			"Please install AWS CLI and SRA Toolkit."
		)


def unique_output_paths(out_dir: Path, sample_name: str, accession: str) -> tuple[Path, Path]:
	base = sanitize_filename(sample_name)
	r1 = out_dir / f"{base}_R1.fastq"
	r2 = out_dir / f"{base}_R2.fastq"
	if not r1.exists() and not r2.exists():
		return r1, r2

	with_accession = sanitize_filename(f"{base}_{accession}")
	return out_dir / f"{with_accession}_R1.fastq", out_dir / f"{with_accession}_R2.fastq"


def process_row(accession: str, sample_name: str, out_dir: Path, work_dir: Path, skip_existing: bool) -> None:
	accession = accession.strip()
	sample_name = sample_name.strip()
	if not accession:
		raise ValueError("Empty accession value")
	if not sample_name:
		raise ValueError(f"Empty sample name for accession {accession}")

	sra_path = work_dir / f"{accession}.sra"
	temp_extract_dir = work_dir / f"{accession}_extract"
	temp_extract_dir.mkdir(parents=True, exist_ok=True)

	final_r1, final_r2 = unique_output_paths(out_dir, sample_name, accession)
	if skip_existing and final_r1.exists() and final_r2.exists():
		print(f"[SKIP] {accession} -> outputs already exist")
		return

	s3_uri = f"{SRA_BUCKET_PREFIX}/{accession}/{accession}"
	print(f"[DOWNLOAD] {s3_uri} -> {sra_path}")
	run_command(["aws", "s3", "cp", s3_uri, str(sra_path)], stream_output=True)

	print(f"[EXTRACT] {sra_path}")
	run_command(
		[
			"fasterq-dump",
			str(sra_path),
			"--split-files",
			"--outdir",
			str(temp_extract_dir),
		]
	)

	extracted_r1 = temp_extract_dir / f"{accession}_1.fastq"
	extracted_r2 = temp_extract_dir / f"{accession}_2.fastq"

	if not extracted_r1.exists() or not extracted_r2.exists():
		raise RuntimeError(
			f"Expected paired FASTQ files were not generated for {accession}: "
			f"{extracted_r1.name}, {extracted_r2.name}"
		)

	final_r1.parent.mkdir(parents=True, exist_ok=True)
	extracted_r1.replace(final_r1)
	extracted_r2.replace(final_r2)

	if sra_path.exists():
		sra_path.unlink()

	if temp_extract_dir.exists():
		for leftover in temp_extract_dir.iterdir():
			leftover.unlink()
		temp_extract_dir.rmdir()

	print(f"[DONE] {accession} -> {final_r1.name}, {final_r2.name}")


def main() -> int:
	args = parse_args()
	csv_path = Path(args.csv)
	out_dir = Path(args.out_dir)
	work_dir = Path(args.work_dir)

	if not csv_path.exists():
		print(f"CSV file not found: {csv_path}", file=sys.stderr)
		return 1

	try:
		ensure_tools_available()
	except RuntimeError as error:
		print(str(error), file=sys.stderr)
		return 1

	out_dir.mkdir(parents=True, exist_ok=True)
	work_dir.mkdir(parents=True, exist_ok=True)

	processed = 0
	failed = 0

	with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		if reader.fieldnames is None:
			print("Input CSV has no header row.", file=sys.stderr)
			return 1

		if args.accession_column not in reader.fieldnames:
			print(
				f"Missing accession column '{args.accession_column}'. "
				f"Available columns: {', '.join(reader.fieldnames)}",
				file=sys.stderr,
			)
			return 1

		if args.sample_column not in reader.fieldnames:
			print(
				f"Missing sample column '{args.sample_column}'. "
				f"Available columns: {', '.join(reader.fieldnames)}",
				file=sys.stderr,
			)
			return 1

		for row_number, row in enumerate(reader, start=2):
			accession = (row.get(args.accession_column) or "").strip()
			sample_name = (row.get(args.sample_column) or "").strip()

			if not accession and not sample_name:
				continue

			try:
				process_row(
					accession=accession,
					sample_name=sample_name,
					out_dir=out_dir,
					work_dir=work_dir,
					skip_existing=args.skip_existing,
				)
				processed += 1
			except Exception as error:
				failed += 1
				print(f"[ERROR] row {row_number}: {error}", file=sys.stderr)

	print(f"Completed. Success: {processed}, Failed: {failed}")
	return 0 if failed == 0 else 2


if __name__ == "__main__":
	raise SystemExit(main())
