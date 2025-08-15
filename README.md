# Harmony Metadata Annotator

This service updates the metadata attributes of an input file to values that
are known to be correct, either amending, adding or deleting attributes as
appropriate. The underlying methodology is to use a configuration file with
[earthdata-varinfo](https://github.com/nasa/earthdata-varinfo) to supply known
corrections to the metadata.

## Directory structure

```
📁
├── .📁 github
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

* `.github` - Contains CI/CD workflows and pull request template.
* `CHANGELOG.md` - Contains a record of changes applied to each new release
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

## Developer Notes

### Local development

Local testing of service functionality can be achieved via a local instance of
[Harmony](https://github.com/nasa/harmony) aka Harmony-In-A-Box. Please see instructions there
regarding creation of a local Harmony instance.

For local development and testing of library modifications or small functions independent of the main Harmony application:

1. Create a Python virtual environment
1. Install the dependencies in `requirements.txt`, and `tests/test_requirements.txt`
1. Install the pre-commit hooks ([described below](#pre-commit-hooks)).

### Creating spatial dimension variables

SMAP L3 collections are missing spatial dimension variables. This service can generate them by using a combination of required CF-compliant attributes and temporary helper attributes.

**Temporary attributes** are identified by a `_*` prefix. They are defined in the earthdata-varinfo configuration and made available in the VarInfoFromNetCDF4 object for use in annotations. These attributes are not written to the DataTree object or the NetCDF output file.

#### Required attributes
- `standard_name` — Must be either `projection_x_coordinate` or `projection_y_coordinate` (per CF conventions).
- `grid_mapping` — References a properly configured grid mapping variable.
- `_*master_geotransform` — Defines the grid details used to generate dimension scales and must be included in the grid mapping variable configuration.
  **One of the following is also required**:
  - `_*corner_point_offsets` — Indicates that the index range should be parsed from the `history` metadata attribute.
  - `_*subset_index_reference` — Indicates that the index range should be obtained from the referenced row or column grid variable. The referenced variable must be configured as an ancillary variable in [harmony-opendap-subsetter](https://github.com/nasa/harmony-opendap-subsetter/) to ensure it is always available to the metadata-annotator.


#### Example SPL3SMAP Metadata Override configuration for creating a spatial dimension:
```
    {
      "Applicability": {
        "Mission": "SMAP",
        "ShortNamePath": "SPL3SMAP",
        "VariablePattern": "/Soil_Moisture_Retrieval_Data/y"
      },
      "Attributes": [
        {
          "Name": "standard_name",
          "Value": "projection_y_coordinate"
        },
        {
          "Name": "long_name",
          "Value": "y coordinate of projection"
        },
        {
          "Name": "dimensions",
          "Value": "y"
        },
        {
          "Name": "axis",
          "Value": "Y"
        },
        {
          "Name": "units",
          "Value": "m"
        },
        {
          "Name": "type",
          "Value": "float64"
        },
        {
          "Name": "_*corner_point_offsets",
          "Value": "history_subset_index_ranges"
        }
      ],
      "_Description": "The pseudo-dimension variable is supplemented with variable attributes (as if it was a dimension variables) to fully specify the Y dimension."
    },
    {
      "Applicability": {
        "Mission": "SMAP",
        "ShortNamePath": "SPL3SMAP",
        "VariablePattern": "/Soil_Moisture_Retrieval_Data/.*"
      },
      "Attributes": [
        {
          "Name": "grid_mapping",
          "Value": "/EASE2_global_projection_9km"
        }
      ],
      "_Description": "SMAP L3 collections omit global grid mapping information"
    },
    {
      "Applicability": {
        "Mission": "SMAP",
        "ShortNamePath": "SPL3SMAP",
        "VariablePattern": "/EASE2_global_projection_9km"
      },
      "Attributes": [
        {
          "Name": "grid_mapping_name",
          "Value": "lambert_cylindrical_equal_area"
        },
        {
          "Name": "standard_parallel",
          "Value": 30.0
        },
        {
          "Name": "longitude_of_central_meridian",
          "Value": 0.0
        },
        {
          "Name": "false_easting",
          "Value": 0.0
        },
        {
          "Name": "false_northing",
          "Value": 0.0
        },
        {
          "Name": "horizontal_datum_name",
          "Value": "WGS84"
        },
        {
          "Name": "inverse_flattening",
          "Value": 298.257223563
        },
        {
          "Name": "semi_major_axis",
          "Value":  6378137.0
        },
        {
          "Name": "semi_minor_axis",
          "Value": 6356752.314245
        },
        {
          "Name": "_*master_geotransform",
          "Value": [-17367530.4451615, 9008.055210146, 0, 7314540.8306386, 0, -9008.055210146]
        }
      ],
      "_Description": "Provide missing global grid mapping attributes for SMAP L3 collections."
    },
```

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
