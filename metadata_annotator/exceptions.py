"""Module defining custom exceptions."""


class MetadataAnnotatorError(Exception):
    """Base error class for exceptions raised by metadata_annotator library."""

    def __init__(self, message=None):
        """All Metadata Annotator service errors have a message field."""
        self.message = message


class InvalidSpatialDimensionType(MetadataAnnotatorError):
    """Raised when a spatial dimension type is not 'x' or 'y'."""

    def __init__(self, spatial_dimension_type):
        """Initialize the exception with the spatial dimension type."""
        super().__init__(f'Invalid spatial dimension type: "{spatial_dimension_type}"')


class MissingDimensionAttribute(MetadataAnnotatorError):
    """Raised when a required metadata attribute is missing from a dimension."""

    def __init__(self, variable_name, attribute_name):
        """Initialize the exception with the variable name and attribute name."""
        super().__init__(
            f'Dimension variable "{variable_name}" does not have '
            f'an associated "{attribute_name}" metadata attribute.',
        )


class InvalidDimensionAttribute(MetadataAnnotatorError):
    """Raised when a dimension variable's metadata attribute is present but invalid."""

    def __init__(self, variable_name, attribute_name, attribute_value):
        """Initialize the exception with variable name, attribute name, and value."""
        super().__init__(
            f'Dimension variable "{variable_name}" has an invalid "{attribute_name} '
            f'value: "{attribute_value}".'
        )


class InvalidGridMappingReference(MetadataAnnotatorError):
    """Raised when the grid mapping variable is missing in earthdata_varinfo."""

    def __init__(self, grid_mapping_reference):
        """Initialize the exception with the grid mapping reference."""
        super().__init__(
            f'Could not find grid mapping reference variable '
            f'"{grid_mapping_reference}"',
        )


class MissingSubsetIndexReference(MetadataAnnotatorError):
    """Raised when the row or column index variable is missing in earthdata_varinfo."""

    def __init__(self, variable_name):
        """Initialize the exception with the row/col index reference variable."""
        super().__init__(
            f'Could not find row/column index reference variable "{variable_name}"',
        )


class InvalidSubsetIndexShape(MetadataAnnotatorError):
    """Raised when the index variable does not have at least two dimensions."""

    def __init__(self, variable_name):
        """Initialize the exception with the row/col index reference variable."""
        super().__init__(
            f'The row/column index reference variable '
            f'"{variable_name}" must have at least two dimensions.'
        )


class MissingStartIndexConfiguration(MetadataAnnotatorError):
    """Raised when method to select start index configuration is missing.

    A dimension variable require's a valid attribute to dictate which method to use to
    select the start index.
    """

    def __init__(self, dimension_name):
        """Initialize the exception with the dimension name."""
        super().__init__(
            f'Missing index range configuration attribute for dimension variable '
            f'"{dimension_name}"',
        )
