"""Utility functionality only needed by the Harmony Metadata Annotator adapter."""

from mimetypes import guess_type


def get_mimetype(file_path: str) -> str:
    """Retrieve MIME type from a file path.

    ".nc4" files are not recognised, so capture that edge-case.

    """
    raw_mime_type, _ = guess_type(file_path)

    if raw_mime_type is not None:
        mime_type = raw_mime_type
    elif file_path.endswith('.nc4'):
        mime_type = 'application/x-netcdf'
    else:
        # Arbitrary binary data (catch-all)
        mime_type = 'application/octet-stream'

    return mime_type
