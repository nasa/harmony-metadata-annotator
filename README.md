# Harmony Metadata Annotator

This prototype service updates the metadata attributes of an input file to
values that are known to be correct, either amending, adding or deleting
attributes as appropriate. The underlying methodology is to use a configuration
file with `earthdata-varinfo` to supply known corrections to the metadata.

## Directory structure

```
📁
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── 📁 bin
├── dev_requirements.txt
├── 📁 docker
├── 📁 harmony_service
├── 📁 metadata_annotator
├── requirements.txt
└── 📁 tests
```

* `CHANGELOG.md` -   Contains a record of changes applied to each new release
  of the Harmony Metadata Annotator Service.
* `CONTRIBUTING.md` -  Instructions on how to contribute to the repository.
* `LICENSE` - Required for distribution under NASA open-source approval.
  Details conditions for use, reproduction and distribution.
* `README.md` - This file, containing guidance on developing the library and service.
* `bin` - A directory containing utility scripts to build the service and test
  images. A script to extract the release notes for the most recent version, as
  contained in `CHANGELOG.md` is also in this directory.
* `dev_requirements.txt` - Contains a list of Python packages required for local
  development, but not for the service itself.
* `docker` - A directory containing the Dockerfiles for the service and test
  images. It also contains `service_version.txt`, which contains the semantic
  version number of the library and service image. Update this file with a new
  version to trigger a release.
* `harmony_service` - A directory containing the Harmony Service specific Python
  code. `adapter.py` contains the `MetadataAnnotatorAdapter` class that is
  invoked by calls to the Harmony service.
* `metadata_annotator` - Directory containing business logic for the service,
  including Harmony scaffolding, such as the adapter class for the service.
* `requirements.txt` - Contains a list of Python packages needed to run the service.
* `tests` -  Contains the `pytest` test suite.

## Local development

Local testing of service functionality can be achieved via a local instance of
[Harmony](https://github.com/nasa/harmony) aka Harmony-In-A-Box. Please see instructions there
regarding creation of a local Harmony instance.

For local development and testing of library modifications or small functions independent of the main Harmony application:

1. Create a Python virtual environment
1. Install the dependencies in `pip_requirements.txt`, and `tests/pip_test_requirements.txt`
1. Install the pre-commit hooks ([described below](#pre-commit-hooks)).

## Enabling the prototype in Harmony in a Box:

To test this service you will need to update your local version of Harmony:

First define the service chain in `services.yml` (at the top of the UAT section):

```
  - name: harmony/harmony-metadata-annotator
    description: |
      Prototype service that creates, updates or deletes metadata attributes of
      NetCDF-4 or HDF-5 files.
      In practice would be used as part of a larger service chain.
    data_operation_version: '0.20.0'
    type:
      <<: *default-turbo-config
      params:
        <<: *default-turbo-params
        env:
          <<: *default-turbo-env
          STAGING_PATH: public/harmony/harmony-metadata-annotator
    umm_s: S1273103184-EEDTEST
    maximum_sync_granules: 0
    capabilities:
      subsetting:
        bbox: false
        variable: false
        multiple_variable: false
      reprojection: false
      concatenation: false
      all_collections: true
      output_formats:
        - application/netcdf # Incorrect mime-type, remove when no longer needed
        - application/x-netcdf4
        - application/x-hdf5
        - application/x-hdf
    steps:
      - image: !Env ${QUERY_CMR_IMAGE}
        is_sequential: true
      - image: !Env ${HARMONY_METADATA_ANNOTATOR_IMAGE}
```

Note the `all_collections` part of the configuration. This allows local testing
without disrupting UMM-C to UMM-S associations for other developers (and SIT or
UAT Harmony environments).

Also note that the Harmony Metadata Annotator is more realistically a step in
a chain, not a chain in and of itself.

Next, define the service queue URLs for SQS (in localstack) in
`packages/util/env-defaults`:

```
HARMONY_METADATA_ANNOTATOR_SERVICE_QUEUE_URLS='["ghcr.io/nasa/harmony-metadata-annotator:latest,http://
sqs.us-west-2.localhost.localstack.cloud:4566/000000000000/harmony-metadata-annotator.fifo"]'
```
Now define the environment variables Harmony will use to set the configuration
of the service Docker containers. Note, for now, that the memory limit is large
due to the way `xarray.DataTree.to_netcdf` uses a lot of memory.

```
HARMONY_METADATA_ANNOTATOR_IMAGE=ghcr.io/nasa/harmony-metadata-annotator:latest
HARMONY_METADATA_ANNOTATOR_REQUESTS_MEMORY=128Mi
HARMONY_METADATA_ANNOTATOR_LIMITS_MEMORY=8Gi
HARMONY_METADATA_ANNOTATOR_INVOCATION_ARGS='python -m harmony_service'
```

Now, try a sample request:

```
http://localhost:3000/C1246896616-EEDTEST/ogc-api-coverages/1.0.0/collections/all/coverage/rangeset?maxResults=1&format=application%2Fx-netcdf4
```

To see that this request worked download the output (using `localhost:3000/jobs`
to find the results URL). Then open that file in Panoply. First note the new CRS
variables in the root group of the output: `/EASE2_global_projection` and
`/EASE2_polar_projection_9km`. These were defined in the
`earthdata_varinfo_config.json` file. Next look at one of the variables, e.g.:
`/Soil_Moisture_Retrieval_Data_AM/albedo`. This will now have a `grid_mapping`
metadata attribute, which was absent in the native data.

## Tests

This service utilises the Python `pytest` package to perform unit tests on
classes and functions in the service. After local development is complete, and
test have been updated, they can be run in Docker via:

```bash
$ ./bin/build-image && ./bin/build-test && ./bin/run-test
```

It is also possible to run the test scripts directly (without Docker) by just
running the `run_tests.sh` script with a proper Python environment. Do note
that the `reports` directory will appear in the directory you call the script from.

The `tests/run_tests.sh` script will also generate a coverage report, rendered
in HTML, and scan the code with `pylint`.

Currently, the `pytest` suite is run automatically within a GitHub workflow
as part of a CI/CD pipeline. These tests are run for all changes made in a PR
against the `main` branch. The tests must pass in order to merge the PR.

## `pre-commit` hooks

This repository uses [pre-commit](https://pre-commit.com/) to enable pre-commit
checks that enforce coding standard best practices. These include:

* Removing trailing whitespaces.
* Removing blank lines at the end of a file.
* Ensure JSON files have valid formats.
* [ruff](https://github.com/astral-sh/ruff) Python linting checks.
* [black](https://black.readthedocs.io/en/stable/index.html) Python code
  formatting checks.
* Ensuring no committed files are above 500 kB.

To enable these checks:

```bash
# Install pre-commit Python package via the listed development requirements:
pip install -r dev_requirements.txt

# Install the git hook scripts:
pre-commit install
```

## Versioning

Docker service images for the `harmony-metadata-annotator` adhere to [semantic
version](https://semver.org/) numbers: major.minor.patch.

* Major increments: These are non-backwards compatible API changes.
* Minor increments: These are backwards compatible API changes.
* Patch increments: These updates do not affect the API to the service.

## Gotchas:

The service currently uses `xarray.DataTree.to_netcdf` to write the whole
`DataTree` object out to a file. This is _very_ memory intensive, meaning that
the Harmony in a Box configuration listed above uses 8 GiB for the memory limit
of the service. A future improvement would be to find a way to write things out
incrementally. The Harmony SMAP L2 Gridder does perform such an operation, and
may be a good model to update this code.
