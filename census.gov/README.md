# fips-lookup.py

Look up 12-digit Census Block Group FIPS codes for a list of addresses using
the Census Bureau's [Batch Geocoding Service](https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html).

The 12-digit FIPS code is `STATE (2) + COUNTY (3) + TRACT (6) + BLOCK GROUP (1)`.

## Requirements

```bash
pip install requests
```

## Input CSV format

Any CSV with columns containing street, city, state, and ZIP. Column names
are configurable (see below); defaults are `street`, `city`, `state`, `zip`.

```csv
street,city,state,zip
4600 Silver Hill Rd,Washington,DC,20233
```

## Usage

```bash
./fips-lookup.py addresses.csv fips_results.csv
```

With custom column names and a specific benchmark/vintage:

```bash
./fips-lookup.py addresses.csv fips_results.csv \
    --street-column address1 --city-column city \
    --state-column state --zip-column zip_code \
    --benchmark Public_AR_Current --vintage Census2020_Current
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--street-column` | `street` | Input column with the street address |
| `--city-column` | `city` | Input column with the city |
| `--state-column` | `state` | Input column with the state |
| `--zip-column` | `zip` | Input column with the ZIP code |
| `--benchmark` | `Public_AR_Current` | Which address-range snapshot to match addresses against |
| `--vintage` | `Current_Current` | Which geography (block/tract/county boundaries) to report FIPS codes from |
| `--batch-size` | `500` | Addresses per API request (API max: 10,000; smaller batches are more reliable) |
| `--retries` | `5` | Retries per failed batch request, with exponential backoff |
| `--timeout` | `600` | Per-request timeout in seconds |

Run `./fips-lookup.py --help` for the full list.

## Output CSV

The output contains all original input columns plus:

| Column | Description |
| --- | --- |
| `match` | Match status returned by the geocoder: `Match`, `No_Match`, or `Tie` (multiple equally-likely matches found, so none was returned) |
| `match_type` | `Exact` if the input address matched as given, `Non_Exact` if the geocoder made corrections (e.g. spelling) to find a match. Empty if not matched |
| `matched_address` | The standardized address string the geocoder matched to. Empty if not matched |
| `longitude` | Longitude (X) of the matched location. Empty if not matched |
| `latitude` | Latitude (Y) of the matched location. Empty if not matched |
| `tigerline_id` | ID of the TIGER/Line address-range segment the match was interpolated from. Empty if not matched |
| `tigerline_side` | Which side of the street segment (`L` left or `R` right) the address falls on. Empty if not matched |
| `state_fips` | 2-digit state FIPS code for the matched location. Empty if not matched |
| `county_fips` | 3-digit county FIPS code for the matched location. Empty if not matched |
| `tract_fips` | 6-digit census tract code for the matched location. Empty if not matched |
| `block_fips` | 4-digit census block code for the matched location. Empty if not matched |
| `fips12` | 12-digit census block group FIPS code (`state_fips` + `county_fips` + `tract_fips` + first digit of `block_fips`). Empty if not matched |
| `error` | Populated with `match` set to `Error` only when the entire batch containing this row failed after all retries (e.g. repeated 502s). Empty otherwise |

`fips12` (and the other geography columns) are empty when an address fails
to match (`match` will be `No_Match` or `Tie`), and also when `match` is
`Error`.

## Understanding `--benchmark` vs `--vintage`

These two parameters control different things, and mixing them up is the
most common source of confusion:

- **`--benchmark`** selects which snapshot of the MAF/TIGER **address
  ranges** is used to actually find/match the input address text to a
  coordinate. A newer benchmark (e.g. `Public_AR_Current`) generally has the
  broadest, most up-to-date address coverage and the best match rate, even
  for older addresses.
- **`--vintage`** selects which snapshot of **geographic boundaries**
  (state/county/tract/block) is used to look up the FIPS code for that
  matched coordinate. Tract and block boundaries are redrawn with every
  decennial census, so the *same* lat/lon can fall into a different FIPS
  code depending on the vintage you choose.

You can discover valid values with:

```
https://geocoding.geo.census.gov/geocoder/benchmarks
https://geocoding.geo.census.gov/geocoder/vintages?benchmark=<benchmarkId>
```

## Matching older addresses to current (2020) census block data

If you have a list of older addresses (e.g. from 2010-era records) and want
their **current 2020 census block/tract FIPS codes** rather than the FIPS
codes that were in effect when the addresses were recorded, keep the
benchmark on `Public_AR_Current` (best match rate for the address text
itself) but set the vintage to the 2020 geography:

```bash
./fips-lookup.py old_addresses.csv fips_results.csv \
    --benchmark Public_AR_Current --vintage Census2020_Current
```

If instead you want FIPS codes as they existed at the time of the **2010**
census (e.g. to join against older Census datasets), use:

```bash
./fips-lookup.py old_addresses.csv fips_results.csv \
    --benchmark Public_AR_Current --vintage Census2010_Current
```

If you specifically need the address matched against the snapshot of
addresses/boundaries used **during the 2020 census itself** (rather than
today's current address ranges), use the matching benchmark/vintage pair:

```bash
./fips-lookup.py addresses.csv fips_results.csv \
    --benchmark Public_AR_Census2020 --vintage Census2020_Census2020
```

As a rule of thumb:

- Use `Public_AR_Current` as the benchmark unless you have a specific reason
  to restrict matching to an older address snapshot.
- Pick the `vintage` based on which census/ACS year's geography boundaries
  you need the FIPS code to align with (`Census2010_Current`,
  `Census2020_Current`, `ACS2023_Current`, etc.).

## Troubleshooting: `502 Server Error` / failed batches

The Census batch geocoder is a shared public service and occasionally returns
`502`/`503`/`504` errors under load, especially for larger batches. The
script automatically retries each batch (`--retries`, default 5) with
exponential backoff before giving up.

If a batch still fails after all retries, the script **does not abort the
whole run**: it marks every row in that batch with `match=Error` (and a
message in the `error` column), prints a warning listing the affected row
ranges, and continues processing the remaining batches so you don't lose
work that already succeeded. To recover the failed rows, either:

- Re-run the script against just those rows (e.g. extract them to a separate
  CSV using the row ranges printed in the warning), or
- Re-run the whole input with a smaller `--batch-size` (e.g. `200`), which
  reduces the chance of timeouts/502s on any single request.

The script exits with a non-zero status code when any batch ultimately
fails, so it's safe to check for this in automated/scripted runs.
