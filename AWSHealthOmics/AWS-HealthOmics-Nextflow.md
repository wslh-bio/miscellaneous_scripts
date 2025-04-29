# AWS HealthOmics Conversion Guide

This guide is to help step through the process of preparing a Nextflow workflow to be compatible with AWS HealthOmics.

## Step 1. Create the parameter template file
This file is used in AWS HealthOmics to specify the parameters available to HealthOmics and Easy Genomics.

It should look something like this:  
  
*parameter-template.json*
```
{
  "myRequiredParameter1": {
     "description": "this parameter is required",
  },
  "myRequiredParameter2": {
     "description": "this parameter is also required",
     "optional": false
  },
  "myOptionalParameter": {
     "description": "this parameter is optional",
     "optional": true
  }
}   
```
Note: The parameter template file only supports two attributes description and optional.


## Step 2. Create the container manifest file
This file is used to specify the containers that need to be staged in AWS ECR for HealthOmics. The AWS HealthOmics service does not have access to the internet so all containers and resources used by the pipeline need to be staged in the cloud. We will use ECR for storing the images but databases and other resources should be stored in S3.

The container manifest should look something like this:  
  
*container_image_manifest.json*
```
{
    "manifest" : [
        "quay.io/biocontainers/python:3.8.3",
        "quay.io/biocontainers/multiqc:1.25.1--pyhdfd78af_0",
        "quay.io/biocontainers/fastqc:0.12.1--hdfd78af_0",
        "staphb/seqtk:1.4"
    ]
}
```

## Step 3. Create the omics configuration file
This file is used to specify some of the critical pieces required for running a Nextflow workflow in AWS HealthOmics.

1. Specify the critical parameters used by HealthOmics, this includes an `ecr_registry` parameter used to define where the images are located and an `outdir` parameter which is needed by HealthOmics to direct the output so it is available after the run is complete.
```
params {
    ecr_registry = ''
    outdir = '/mnt/workflow/pubdir'
}
```

2. Next we must specify the version of Nextflow to use, currently HealthOmics only supports `v22.04.01` (DSL 1 and 2) and `v23.10.0` (DSL 2). Note only `v23.10.0` supports the nf-validation plugin and neither currently support the nf-schema plugin.
```
manifest {
    nextflowVersion = '!>=23.10'
}
```

3. Disable conda, it is not available or needed in AWS HealthOmics.
```
conda {
    enabled = false
}

process {
withName: '.*' { conda = null }
}
```

4. Enable Docker and set the registry to the correct ECR registry. Note you will need to replace `<account-id>` and `<region>` with the correct values. If you want to parameterize the registry you can set it by changing: `registry = params.ecr_registry`.
```
docker {
    enabled = true
    registry = '<account-id>.dkr.ecr.<region>.amazonaws.com'
}
```

## Step 4. Stage the images in ECR
Use the [AWS-HealthOmics-Container-Deploy.py](https://github.com/wslh-bio/miscellaneous_scripts/blob/main/AWSHealthOmics/AWS-HealthOmics-Container-Deploy.py) script to read the container manifest file created in Step 2 and deploy the containers in AWS ECR. Note: you will need to have established your AWS Credentials in your environment in order to stage the images.
```
python3 AWS-HealthOmics-Container-Deploy.py container_image_manifest.json
```
