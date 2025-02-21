"""`HarmonyAdapter` for Harmony Metadata Annotator service.

The class in this file is the top level of abstraction for a service that will
accept an input file (HDF-5 or NetCDF-4) and update metadata attributes where
needed.

"""

from os.path import basename
from os.path import join as path_join
from pathlib import Path
from tempfile import TemporaryDirectory

from harmony_service_lib import BaseHarmonyAdapter
from harmony_service_lib.message import Source as HarmonySource
from harmony_service_lib.util import download, stage
from pystac import Asset, Item

from harmony_service.utilities import get_mimetype
from metadata_annotator.annotate import annotate_granule

VARINFO_CONFIG_FILE = 'earthdata_varinfo_config.json'


class MetadataAnnotatorAdapter(BaseHarmonyAdapter):
    """Custom adapter for Harmony Metadata Annotator Service."""

    def process_item(self, item: Item, source: HarmonySource) -> Item:
        """Process single input STAC item."""
        with TemporaryDirectory() as working_directory:
            try:
                results = item.clone()
                results.assets = {}

                asset = next(
                    item_asset
                    for item_asset in item.assets.values()
                    if 'data' in (item_asset.roles or [])
                )

                # Download the input:
                input_file_path = download(
                    asset.href,
                    working_directory,
                    logger=self.logger,
                    cfg=self.config,
                    access_token=self.message.accessToken,
                )

                # harmony.util.download generates a random SHA256 hash for the
                # local input file, so the original file name can be reused for
                # now (harmony.util.generate_output_filename does not have an
                # appropriate suffix to add to the file)
                output_filename = basename(asset.href)
                working_file_path = path_join(working_directory, output_filename)

                annotate_granule(
                    input_file_path,
                    working_file_path,
                    VARINFO_CONFIG_FILE,
                    collection_short_name=source.shortName,
                )

                # Retrieve MIME type of output:
                output_mime_type = get_mimetype(output_filename)

                # Stage the transformed output:
                staged_url = stage(
                    working_file_path,
                    output_filename,
                    output_mime_type,
                    location=self.message.stagingLocation,
                    logger=self.logger,
                    cfg=self.config,
                )

                # Add the asset to the results Item
                results.assets['data'] = Asset(
                    staged_url,
                    title=Path(staged_url).name,
                    media_type=output_mime_type,
                    roles=['data'],
                )
                return results

            except Exception as exception:
                self.logger.exception(exception)
                raise exception
