"""Define harmony service errors raised by Harmony Metadata Annotator service."""

from harmony_service_lib.util import HarmonyException

SERVICE_NAME = 'harmony-metadata-annotator'


class MetadataAnnotatorServiceError(HarmonyException):
    """Base service exception."""

    def __init__(self, message=None):
        """All service errors are associated with SERVICE_NAME."""
        super().__init__(message=message, category=SERVICE_NAME)
