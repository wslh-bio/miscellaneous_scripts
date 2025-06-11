import sys
import json
import logging
import argparse

logging.basicConfig(level=logging.INFO, format="%(levelname)s : %(message)s", force=True)

def parse_args():
    description="Convert JSON container definitions to Omics config format for healtomics."
    epilog = "Example usage: python3 convert-to-omics-config.py <input_file.json> <output_destination> <acct_id>"
    parser = argparse.ArgumentParser(description=description, epilog=epilog)
    parser.add_argument("-i",
                        "--input_file",
                        help="Path to the input JSON file containing container definitions.")
    parser.add_argument("-a",
                        "--account_id",
                        help="Account ID for the Omics config file.")
    parser.add_argument("-o",
                        "--output_destination",
                        help="Path to the output Omics config file.")
    return parser.parse_args()

def write_boilerplate(output):
    logging.debug("Writing boilerplate to omics.config")
    boilerplate = """params {
    ecr_registry = ''
    outdir = '/mnt/workflow/pubdir'
}
manifest {
    nextflowVersion = '!>=23.10'
}
conda {
    enabled = false
}
"""

    with open(output, "w") as f:
        f.write(boilerplate)

def go_through_containers(input_file, output):

    logging.debug("Opening container jsons file")
    with open(input_file) as f:
        data = json.load(f)

    process = []
    process.append("process {")
    process.append("    withName: '.*' { conda = null }")

    for proc in data.get("processes", []):
        name = proc["name"]
        container = proc["container"]

        if container.startswith("quay.io/"):
            container = container.replace("quay.io/", "")
        process.append(f"    withName: '(.+:)?{name}' {{ container = '{container}'}}")

    process.append("}")

    with open(output, "a") as f:
        f.write("\n".join(process) + "\n")

def write_docker(account_id, output):
    acct_info = """docker {
    enabled = true
    registry = accountnumber.dkr.ecr.us-east-1.amazonaws.com
}
"""
    acct_info = acct_info.replace("accountnumber", account_id)
    with open(output, "a") as f:
        f.write(acct_info)

def main(args=None):
    args = parse_args()

    output = f"{args.output_destination}/omics.config"

    logging.debug("Adding boilerplate to omics.config")
    write_boilerplate(output)

    logging.debug("Convert the JSON container definitions to Omics config format")
    go_through_containers(args.input_file, output)

    logging.debug("Adding account information to omics.config")
    write_docker(args.account_id, output)

    logging.info("Conversion complete. Output written to omics.config")

if __name__ == "__main__":
    sys.exit(main())