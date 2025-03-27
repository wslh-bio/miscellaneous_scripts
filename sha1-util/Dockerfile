# ╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
# ║ if you don't have python installed, or unable to install dependencies for this script, docker may be ║░
# ║ an option.  The commands below build a docker image, and container, then the script is run in the    ║░
# ║ container. Cleanup is performed by deleting the container after the run. This is done with --rm flag ║░
# ║ and is a good practice to saves disk space and prevents potential data leaks.                        ║░
# ║                                                                                                      ║░
# ║ The source and destination directories must be available in the container so a volume                ║░
# ║ mount is used. In the example below, the source directory is /scratch/source and the destination     ║░
# ║ directory is /scratch/dest. This only needs a single volume mount since the source and destination   ║░
# ║ directories are subdirectories of the scratch directory.                                             ║░
# ║                                                                                                      ║░
# ║ docker build -t tmp-docker .                                                                         ║░
# ║ docker run --rm --volume /scratch:/scratch tmp-docker --source /scratch/source --dest /scratch/dest  ║░
# ║                                                                                                      ║░ 
# ║ If the source and destination directories are not subdirectories of the scratch directory, then      ║░
# ║ multiple volume mounts would be required and the command would look something like this (no need to  ║░
# ║ build the container again):                                                                          ║░
# ║                                                                                                      ║░    
# ║ docker run --rm --volume /shared:/shared --volume /local:/local \                                    ║░
# ║    tmp-docker --source /shared/somefiles/new --dest /local/otherfiles/current                        ║░
# ╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝░
#   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░

FROM alpine:latest

# Install Python and pip
RUN apk add --no-cache python3 py3-pip

# Set the working directory
WORKDIR /app

# Copy the script into the container
COPY sha1-util.py /app/sha1-util.py

# Install any Python dependencies (if needed)
# RUN pip3 install --no-cache-dir -r requirements.txt

# Set the entry point to run the script
ENTRYPOINT ["python3", "/app/sha1-util.py"]


