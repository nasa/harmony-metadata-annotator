###############################################################################
#
# Service image for ghcr.io/nasa/harmony-metadata-annotator, a Harmony backend
# service that amends, adds or deletes metadata attributes of an HDF-5 or
# NetCDF-4 file.
#
# This image instantiates a conda environment, with required pacakges, before
# installing additional dependencies via Pip. The service code is then copied
# into the Docker image, before environment variables are set to activate the
# created conda environment.
#
###############################################################################
FROM python:3.12-slim-bookworm

WORKDIR "/home"

RUN apt-get update

# Install Pip dependencies
COPY requirements.txt /home/

RUN pip install --no-input --no-cache-dir -r requirements.txt

# Copy service code.
COPY ./harmony_service harmony_service
COPY ./metadata_annotator metadata_annotator
COPY ./docker/service_version.txt ./docker/service_version.txt

# Configure a container to be executable via the `docker run` command.
ENTRYPOINT ["python", "-m", "harmony_service"]
