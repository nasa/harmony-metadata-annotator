#!/bin/sh
###############################################################################
# A script invoked by the test Dockerfile to run the `pytest` suite  for the
# Harmony Metadata Annotator Service. The script uses `pytest` an associated
# plugins to ensure the unit tests all pass, determine test coverage of the
# source code and generate JUnit style output. An additional check is performed
# via pylint for linting errors.
###############################################################################

# Exit status used to report back to caller
STATUS=0

# Run the standard set of unit tests, producing JUnit compatible output
pytest --cov=metadata_annotator --cov=harmony_service
       --cov-report=html:reports/coverage \
       --cov-report term \
       --junitxml=reports/test-reports/test-results-"$(date +'%Y%m%d%H%M%S')".xml || STATUS=1

# Run pylint
pylint metadata_annotator harmony_service --disable=W1203
RESULT=$((3 & $?))

if [ "$RESULT" -ne "0" ]; then
    STATUS=1
    echo "ERROR: pylint generated errors"
fi

exit $STATUS
