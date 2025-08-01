# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v1.0.4] - 2025-07-22

### Changed

- Prevent creation of unreferenced grid mapping and dimensions variables.


## [v1.0.3] - 2025-06-25

### Changed

- Add missing fill value attribute to latitude/longitude variables in SPL2SMAP_S, SPL3FTA, SPL3FTP,
  and SPL3FTP_E.
- Remove comma delimiter in coordinates attribute override for SPL3SMP & SPL3SMP_E.


## [v1.0.2] - 2025-06-06

### Changed

- Fixed geotransform metadata on `/EASE2_global_projection_36km`


## [v1.0.1] - 2025-05-28

### Changed

- Update the coordinates attribute metadata override for SPL3SMP and SPL3SMP_E to prevent the
  override on dimension variables. Also, add a metadata override that deletes the coordinate
  attribute on the latitude_pm and longitude_pm variables for SPL3SMP and SPL3SMP_E.

## [v1.0.0] - 2025-05-14

### Changed

- Use the index ranges from the history attribute to calculate the grid start index if configured to do so.
  The dimension scales are then determined based on the projection attributes provided in the associated grid
  mapping variable's `master_geotransform`.
- Update spatial dimension variables with a dimension scale that is computed based off the
  associated grid mapping variable's `master_geotransform` and the determined grid start index.
  Currently, the grid start index can be determined from the dimension's associated row/col index
  variable.
- Update Harmony Metadata Annotator to rename pseudo dimension variables
  that get created in collections that do not have dimension variables.
  Rename the dimension variables with the names provided in the earthdata-varinfo configuration file.
- Update the earthdata varinfo configuration file for SMAP L3 collections to make
  the global grid mapping variables resolution specific, add a `master_geotransform`
  attribute to all grid mapping variables, add missing dimension variables, and create a dimensions
  attribute on their associated variables.

## [v0.0.1] - 2025-03-28

### Added

- This is the first formal release of the Harmony Metadata Annotator as
  as Docker image available through the GitHub Container Registry.
- Service functionality: Ability to create, update, delete metadata attributes
  for a variable as specified via an `earthdata-varinfo` configuration file.
- Initial repository setup with utility scripts and Dockerfiles.

[v1.0.4]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/1.0.4
[v1.0.3]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/1.0.3
[v1.0.2]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/1.0.2
[v1.0.1]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/1.0.1
[v1.0.0]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/1.0.0
[v0.0.1]: https://github.com/nasa/harmony-metadata-annotator/releases/tag/0.0.1
