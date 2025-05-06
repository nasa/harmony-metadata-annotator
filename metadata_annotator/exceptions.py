"""Module defining custom exceptions."""


class MetadataAnnotatorError(Exception):
    """Base error class for exceptions raised by metadata_annotator library."""

    def __init__(self, message=None):
        """All Metadata Annotator service errors have a message field."""
        self.message = message


class InvalidSpatialDimensionType(MetadataAnnotatorError):
    """Raised when a spatial dimension type is not 'x' or 'y'."""

    def __init__(self, spatial_dimension_type):
        """Initialize the exception with the provided spatial dimension type."""
        super().__init__(f'Invalid spatial dimension type: "{spatial_dimension_type}"')
