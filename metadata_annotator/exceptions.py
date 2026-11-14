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


class InvalidDimensionsConfiguration(MetadataAnnotatorError):
    """Raised when a dimension variable's metadata attribute is present but invalid."""

    def __init__(
        self, variable_name, num_configured_dimensions, num_expected_dimensions
    ):
        """Initialize with variable name, configured and expected dimensions."""
        super().__init__(
            f'Incorrect number of configured dimensions for {variable_name}'
            f'Dimension variable "{variable_name}" has "{num_configured_dimensions} '
            f'dimensions instead of "{num_expected_dimensions}".'
        )


class MissingDimensionVariable(MetadataAnnotatorError):
    """Raised when an expected dimension variable is not in the datatree."""

    def __init__(self, variable_name):
        """Initialize the exception with the variable name."""
        super().__init__(f'Dimension variable {variable_name} is not in the datatree.')


class AmbiguousDimensionVariables(MetadataAnnotatorError):
    """Raised when two requested dimension variables share a source dimension."""

    def __init__(self, group_path, first_variable, second_variable, dimension):
        """Initialize the exception with the group, the variables and the dimension."""
        super().__init__(
            f'Variables "{first_variable}" and "{second_variable}" in group '
            f'"{group_path}" both span dimension "{dimension}", so neither can be '
            'swapped for it. Square grids without dimension scales are not '
            'supported.'
        )


class InvalidHDFEOS5GridDefinition(MetadataAnnotatorError):
    """Raised when an HDF-EOS5 grid is missing, unsupported or misconfigured."""

    def __init__(self, item_name, reason):
        """Initialize the exception with the grid or variable name and reason."""
        super().__init__(
            f'Invalid HDF-EOS5 grid configuration for "{item_name}": {reason}.'
        )


class UnexpectedCoordinateValues(MetadataAnnotatorError):
    """Raised when coordinates match neither pixel corners nor pixel centers."""

    def __init__(self, variable_name):
        """Initialize the exception with the coordinate variable name."""
        super().__init__(
            f'Coordinate variable "{variable_name}" matches neither the pixel '
            'corners nor the pixel centers of its HDF-EOS5 grid definition.'
        )
