#!/usr/bin/env python3

import os,sys
import boto3
from botocore.config import Config
import json
import argparse
import logging
import docker
import base64

# initialize logging
logging.basicConfig(level = logging.INFO, format = '%(levelname)s : %(message)s', force = True)

# Set up argument parser
class MyParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write("error: %s" % message)
        self.print_help()
        sys.exit(2)

parser = MyParser()
parser.add_argument("container_manifest",help="Location of container manifest (json)")
parser.add_argument("--region", default="us-east-1", help="Set the AWS Region, Default: us-east-1")

args = parser.parse_args()

# initialize clients
boto3_config = Config(region_name=args.region)
ecr_client = boto3.client('ecr',config=boto3_config)
docker_client = docker.from_env()



### Get AWS ECR Auth Token (Valid for 12 hours)
ecr_auth_response = ecr_client.get_authorization_token()

ecr_username, ecr_password = base64.b64decode(ecr_auth_response['authorizationData'][0]['authorizationToken']).decode("utf-8").split(":")
ecr_registry = ecr_auth_response['authorizationData'][0]['proxyEndpoint'].replace("https://",'')
logging.info(f'ECR Authorization Obtained, expires: {ecr_auth_response['authorizationData'][0]['expiresAt']}')

### Create AWS ECR Auth
ecr_auth_config = {
    'username':ecr_username, 
    'password':ecr_password,
    'registry':ecr_registry
}

### Create AWS ECR Access Policy
ecr_repository_access_policy = {
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "omics workflow access",
      "Effect": "Allow",
      "Principal": {
        "Service": "omics.amazonaws.com"
      },
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer"
      ]
    }
  ]
}

### Get containers and transfer to ECR
with open(args.container_manifest,'r') as infile:
    container_data = json.load(infile)

for container in container_data['manifest']:
    sha = None
    # Pull Container using Docker
    if "@" in container:
        repository,sha = container.split("@")
        tag = sha.split(":")[1]
        logging.info(f"Pulling Docker Image: {repository}@{sha}")
        original_image = docker_client.images.pull(repository,sha)
    else:
        repository,tag = container.split(":")
        logging.info(f"Pulling Docker Image: {repository}:{tag}")
        original_image = docker_client.images.pull(repository,tag)

    image_digests = original_image.attrs['RepoDigests'] 

    # Create AWS ECR Repository ID if Needed
    if "." in repository.split("/")[0]:
        ecr_repository = "/".join(repository.split("/")[1:])
    else:
        ecr_repository = repository

    try:
        response = ecr_client.describe_repositories(repositoryNames=[ecr_repository])
        logging.info(f"Found existing ECR repository for: {ecr_repository}")
        repositoryURI = response['repositories'][0]['repositoryUri']
    except ecr_client.exceptions.RepositoryNotFoundException:
        logging.info(f"Creating new ECR repository for: {ecr_repository}")
        response = ecr_client.create_repository(
            repositoryName = ecr_repository,
            imageScanningConfiguration={'scanOnPush': False}
        )
        repositoryURI = response['repository']['repositoryUri']
        logging.info(f"Setting policy for AWS HealthOmics access.")
        response = ecr_client.set_repository_policy(
            repositoryName = ecr_repository,
            policyText = json.dumps(ecr_repository_access_policy)
        )

    # Re-tag and Push image to ECR
    ecr_image = original_image.tag(repositoryURI,tag)
    logging.info(f"Pushing {repositoryURI}:{tag}")
    response = docker_client.images.push(repository= repositoryURI,tag= tag,auth_config= ecr_auth_config, stream=True,decode=True)
    for data in response:
        id = data.get('id')
        progress = data.get('progress')
        if id and progress:
            logging.info(f"Layer: {id} {progress}")
    
    if sha:
        response = ecr_client.describe_images(
            repositoryName= ecr_repository, 
            imageIds = [
                {'imageDigest': sha,'imageTag': tag}
            ]
        )
        try:
            logging.info(f"Successfully Pushed {response['imageDetails'][0]['repositoryName']} with Digest: {response['imageDetails'][0]['imageDigest']}")
        except:
            logging.error(f"Issues occurred when pushing {ecr_repository} or when verifying correct image digest.")
    else:
        logging.info(f'Successfully Pushed {ecr_repository}:{tag}')