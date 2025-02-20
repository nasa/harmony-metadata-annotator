#!/bin/bash
##################################################################################
#
# Extract release notes for the latest version of Harmony CF Annotator service
#
##################################################################################

CHANGELOG_FILE="CHANGELOG.md"

## captures versions
## >## v1.0.0
## >## [v1.0.0]
VERSION_PATTERN="^## [\[]v"

## captures url links
## [unreleased]:https://github.com/nasa/harmony-cf-annotator/compare/1.2.0..HEAD
## [v1.2.0]: https://github.com/nasa/harmony-cf-annotator/compare/1.1.0..1.2.0
LINK_PATTERN="^\[.*\].*releases/tag/.*"

# Read the file and extract text between the first two occurrences of the
# VERSION_PATTERN
result=$(awk "/$VERSION_PATTERN/{c++; if(c==2) exit;} c==1" "$CHANGELOG_FILE")

# Print the result
echo "$result" |  grep -v "$VERSION_PATTERN" | grep -v "$LINK_PATTERN"
