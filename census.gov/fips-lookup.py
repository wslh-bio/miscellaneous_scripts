#!/usr/bin/env python3
"""
fips-lookup.py

Look up 12-digit Census Block Group FIPS codes (STATE+COUNTY+TRACT+BLOCK GROUP)
for a list of addresses using the Census Bureau's Batch Geocoding Service:

    https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html

Reads addresses from an input CSV, submits them in batches (max 10,000 rows
per request, per the API) to the "geographies/addressbatch" endpoint, and
writes a new CSV with the original columns plus the match status, matched
address, coordinates, and the 12-digit FIPS code.

The benchmark/vintage (i.e. which "snapshot" of Census geography to match
against) is configurable on the command line. Valid values can be discovered
at:

    https://geocoding.geo.census.gov/geocoder/benchmarks
    https://geocoding.geo.census.gov/geocoder/vintages?benchmark=<benchmarkId>

Requires the third-party `requests` package: pip install requests

Example:
    ./fips-lookup.py addresses.csv fips_results.csv \\
        --street-column address --city-column city \\
        --state-column state --zip-column zip \\
        --benchmark Public_AR_Census2020 --vintage Census2020_Census2020
"""

import argparse
import csv
import io
import sys
import time
from pathlib import Path

import requests

BATCH_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
MAX_BATCH_SIZE = 10000

OUTPUT_FIELDS = [
	"match",
	"match_type",
	"matched_address",
	"longitude",
	"latitude",
	"tigerline_id",
	"tigerline_side",
	"state_fips",
	"county_fips",
	"tract_fips",
	"block_fips",
	"fips12",
	"error",
]

# Census batch geocoder occasionally returns 502/503/504 under load, especially
# for large batches. These are worth retrying with backoff.
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description=(
			"Geocode addresses from a CSV file using the Census Bureau Batch "
			"Geocoding Service and output the 12-digit Census Block Group "
			"FIPS code for each address."
		)
	)
	parser.add_argument("input_csv", help="Path to input CSV file of addresses")
	parser.add_argument("output_csv", help="Path to write output CSV file")
	parser.add_argument(
		"--street-column",
		default="street",
		help="Input CSV column containing the street address (default: street)",
	)
	parser.add_argument(
		"--city-column",
		default="city",
		help="Input CSV column containing the city (default: city)",
	)
	parser.add_argument(
		"--state-column",
		default="state",
		help="Input CSV column containing the state (default: state)",
	)
	parser.add_argument(
		"--zip-column",
		default="zip",
		help="Input CSV column containing the ZIP code (default: zip)",
	)
	parser.add_argument(
		"--benchmark",
		default="Public_AR_Current",
		help=(
			"Census geocoder benchmark name or numeric ID identifying the "
			"address locator dataset to use (default: Public_AR_Current). "
			"See https://geocoding.geo.census.gov/geocoder/benchmarks"
		),
	)
	parser.add_argument(
		"--vintage",
		default="Current_Current",
		help=(
			"Census geocoder vintage name or numeric ID identifying the "
			"geography snapshot to match against (default: Current_Current). "
			"See https://geocoding.geo.census.gov/geocoder/vintages?benchmark=<benchmarkId>"
		),
	)
	parser.add_argument(
		"--batch-size",
		type=int,
		default=500,
		help=(
			"Number of addresses to submit per API request, up to the API "
			f"maximum of {MAX_BATCH_SIZE} (default: 500). The Census API tends "
			"to return intermittent 502 errors on large batches, so smaller "
			"values are more reliable."
		),
	)
	parser.add_argument(
		"--retries",
		type=int,
		default=5,
		help="Number of times to retry a failed batch request (default: 5)",
	)
	parser.add_argument(
		"--timeout",
		type=int,
		default=600,
		help="Per-request timeout in seconds (default: 600)",
	)
	return parser.parse_args()


def read_input_rows(input_csv: Path, street_col: str, city_col: str,
                     state_col: str, zip_col: str) -> tuple[list[dict], list[str]]:
	with open(input_csv, newline="", encoding="utf-8-sig") as handle:
		reader = csv.DictReader(handle)
		fieldnames = reader.fieldnames or []
		for column in (street_col, city_col, state_col, zip_col):
			if column not in fieldnames:
				raise ValueError(
					f"Column '{column}' not found in {input_csv}. "
					f"Available columns: {fieldnames}"
				)
		rows = list(reader)
	return rows, fieldnames


def build_batch_payload(rows: list[dict], street_col: str, city_col: str,
                         state_col: str, zip_col: str, start_id: int) -> str:
	buffer = io.StringIO()
	writer = csv.writer(buffer)
	for offset, row in enumerate(rows):
		record_id = start_id + offset
		writer.writerow([
			record_id,
			row.get(street_col, ""),
			row.get(city_col, ""),
			row.get(state_col, ""),
			row.get(zip_col, ""),
		])
	return buffer.getvalue()


def submit_batch(payload: str, benchmark: str, vintage: str, retries: int,
                  timeout: int) -> str:
	data = {"benchmark": benchmark, "vintage": vintage}

	last_error: Exception | None = None
	for attempt in range(1, retries + 1):
		try:
			# Re-create the files dict each attempt: requests consumes the
			# file-like/string body on send, so it can't be reused as-is.
			files = {"addressFile": ("addresses.csv", payload, "text/csv")}
			response = requests.post(
				BATCH_URL, data=data, files=files, timeout=timeout
			)
			if response.status_code in RETRYABLE_STATUS_CODES:
				raise requests.HTTPError(
					f"{response.status_code} Server Error for url: {BATCH_URL}",
					response=response,
				)
			response.raise_for_status()
			return response.text
		except requests.RequestException as exc:
			last_error = exc
			sys.stderr.write(
				f"Batch request failed (attempt {attempt}/{retries}): {exc}\n"
			)
			if attempt < retries:
				wait = min(5 * (2 ** (attempt - 1)), 120)
				sys.stderr.write(f"Retrying in {wait}s...\n")
				time.sleep(wait)
	raise RuntimeError(f"Batch request failed after {retries} attempts") from last_error


def parse_batch_response(response_text: str) -> dict[int, dict]:
	results: dict[int, dict] = {}
	reader = csv.reader(io.StringIO(response_text))
	for fields in reader:
		if not fields:
			continue
		record_id = int(fields[0])
		match_status = fields[2] if len(fields) > 2 else ""
		result = {field: "" for field in OUTPUT_FIELDS}
		result["match"] = match_status

		if match_status == "Match" and len(fields) >= 11:
			match_type = fields[3]
			matched_address = fields[4]
			coordinates = fields[5]
			tigerline_id = fields[6]
			tigerline_side = fields[7]
			state_fips = fields[8]
			county_fips = fields[9]
			tract_fips = fields[10]
			block_fips = fields[11] if len(fields) > 11 else ""
			longitude, _, latitude = coordinates.partition(",")

			fips12 = ""
			if state_fips and county_fips and tract_fips and block_fips:
				fips12 = f"{state_fips}{county_fips}{tract_fips}{block_fips[0]}"

			result.update({
				"match_type": match_type,
				"matched_address": matched_address,
				"longitude": longitude,
				"latitude": latitude,
				"tigerline_id": tigerline_id,
				"tigerline_side": tigerline_side,
				"state_fips": state_fips,
				"county_fips": county_fips,
				"tract_fips": tract_fips,
				"block_fips": block_fips,
				"fips12": fips12,
			})

		results[record_id] = result
	return results


def geocode_rows(rows: list[dict], street_col: str, city_col: str, state_col: str,
                  zip_col: str, benchmark: str, vintage: str, batch_size: int,
                  retries: int, timeout: int) -> tuple[dict[int, dict], list[tuple[int, int]]]:
	batch_size = min(batch_size, MAX_BATCH_SIZE)
	all_results: dict[int, dict] = {}
	failed_ranges: list[tuple[int, int]] = []

	for start in range(0, len(rows), batch_size):
		batch_rows = rows[start:start + batch_size]
		end = start + len(batch_rows)
		print(f"Submitting records {start + 1}-{end} of {len(rows)}...")
		payload = build_batch_payload(
			batch_rows, street_col, city_col, state_col, zip_col, start_id=start
		)
		try:
			response_text = submit_batch(payload, benchmark, vintage, retries, timeout)
		except RuntimeError as exc:
			sys.stderr.write(
				f"Giving up on records {start + 1}-{end} after {retries} attempts: "
				f"{exc}. Continuing with remaining batches.\n"
			)
			failed_ranges.append((start + 1, end))
			for record_id in range(start, end):
				result = {field: "" for field in OUTPUT_FIELDS}
				result["match"] = "Error"
				result["error"] = str(exc)
				all_results[record_id] = result
			continue

		all_results.update(parse_batch_response(response_text))

	return all_results, failed_ranges


def write_output(output_csv: Path, rows: list[dict], fieldnames: list[str],
                  results: dict[int, dict]) -> None:
	out_fieldnames = fieldnames + OUTPUT_FIELDS
	with open(output_csv, "w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=out_fieldnames)
		writer.writeheader()
		for index, row in enumerate(rows):
			result = results.get(index, {field: "" for field in OUTPUT_FIELDS})
			out_row = {**row, **result}
			writer.writerow(out_row)


def main() -> None:
	args = parse_args()
	input_csv = Path(args.input_csv)
	output_csv = Path(args.output_csv)

	rows, fieldnames = read_input_rows(
		input_csv, args.street_column, args.city_column,
		args.state_column, args.zip_column
	)
	if not rows:
		sys.stderr.write(f"No data rows found in {input_csv}\n")
		sys.exit(1)

	results, failed_ranges = geocode_rows(
		rows, args.street_column, args.city_column, args.state_column,
		args.zip_column, args.benchmark, args.vintage, args.batch_size,
		args.retries, args.timeout
	)
	write_output(output_csv, rows, fieldnames, results)

	matched = sum(1 for r in results.values() if r["match"] == "Match")
	print(f"Done. {matched}/{len(rows)} addresses matched. Output written to {output_csv}")

	if failed_ranges:
		ranges_str = ", ".join(f"{lo}-{hi}" for lo, hi in failed_ranges)
		sys.stderr.write(
			f"\nWARNING: {len(failed_ranges)} batch(es) failed and were marked "
			f"'Error' in the output: rows {ranges_str}. Re-run with just those "
			"rows (or a smaller --batch-size) to retry them.\n"
		)
		sys.exit(1)


if __name__ == "__main__":
	main()
