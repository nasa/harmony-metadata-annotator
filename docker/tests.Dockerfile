###############################################################################
#
# Test image for the Harmony Metadata Annotator service. This image uses
# the main service image, ghcr.io/nasa/harmony-metadata-annotator, as a base
# layer for the tests. This ensures  that the contents of the service image are
# tested, preventing discrepancies between the service and test environments.
#
# 2021-06-24: Updated
# 2023-10-06: Updated to use new open-source service image name and new conda
#             environment name.
#
###############################################################################
FROM ghcr.io/nasa/harmony-metadata-annotator

# Install additional Pip requirements (for testing)
COPY tests/test_requirements.txt .

RUN pip install --no-input --no-cache-dir -r test_requirements.txt

# Copy test directory containing Python unittest suite, test data and utilities
COPY ./tests tests

# Configure a container to be executable via the `docker run` command.
ENTRYPOINT ["/home/tests/run_tests.sh"]
