from gettext import gettext as _

import logging
import os
import shutil

from urlparse import urljoin

from nectar import request

from pulp.common.plugins import importer_constants
from pulp.plugins.conduits.mixins import UnitAssociationCriteria
from pulp.plugins.util.publish_step import PluginStep, PluginStepIterativeProcessingMixin, DownloadStep
from pulp.server.managers.content.query import ContentQueryManager
import pulp.server.managers.factory as manager_factory

from pulp_openstack.common import constants, models
from pulp_openstack.common import openstack_utils


_logger = logging.getLogger(__name__)


class GlanceImageSync(PluginStep):
    """
    Openstack Image Sync
    """

    def __init__(self, repo, conduit, config):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param conduit: Conduit providing access to relative Pulp functionality
        :type  conduit: conduit
        :param config: Pulp configuration for the importer
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        super(GlanceImageSync, self).__init__(constants.SYNC_STEP, repo, conduit, config)

        metadata_dl_req_step = GlanceImageMetadataDownloadStep(constants.SYNC_STEP)
        metadata_dl_req_step.description = _('Downloading image metadata')
        self.add_child(metadata_dl_req_step)

        metadata_process_step = GlanceImageDownloadStep(constants.SYNC_STEP)
        metadata_process_step.description = _('Processing metadata and download images')
        self.add_child(metadata_process_step)

    def sync(self):
        """
        kick off the sync
        """
        self.process_lifecycle()
        return self._build_final_report()


class GlanceImageMetadataDownloadStep(DownloadStep):

    def __init__(self, plugin_type):
        super(GlanceImageMetadataDownloadStep, self).__init__(plugin_type)

    def initialize(self):
        """
        sets up a download request for metadata.

        Note that after this step is done, anything in self.downloads will get downloaded.
        """
        super(GlanceImageMetadataDownloadStep, self).initialize()
        config = self.get_config()
        repo_url = config.get(importer_constants.KEY_FEED)
        manifest_url = urljoin(repo_url, models.ImageManifest.FILENAME)
        manifest_destination = os.path.join(self.get_working_dir(), models.ImageManifest.FILENAME)
        self.downloads.append(request.DownloadRequest(manifest_url, manifest_destination))


class GlanceImageDownloadStep(DownloadStep):

    def __init__(self, plugin_type):
        super(GlanceImageDownloadStep, self).__init__(plugin_type)

    def _get_total(self):
        """
        process metadata and creates a list of new units to create and download

        This is a little unusual in that we are doing initialize() code inside
        of _get_total(). We need to know how many items we are processing ASAP,
        before initialize() happens, so we can set the length of the progress bar.
        Unfortunately, we need to do metadata processing in order to figure out how
        many items are being downloaded.

        :returns: number of items to download
        :rtype: int

        """
        # set up the downloader
        super(GlanceImageDownloadStep, self).initialize()

        metadata = self._get_metadata()
        config = self.get_config()
        conduit = self.get_conduit()
        repo_url = config.get(importer_constants.KEY_FEED)

        association_manager = manager_factory.repo_unit_association_manager()

        # find all images we know of in pulp
        query_manager = ContentQueryManager()
        local_image_unit_coll = query_manager.\
                                  get_content_unit_collection(type_id=constants.IMAGE_TYPE_ID)
        local_image_units = list(local_image_unit_coll.find())

        # this is a little verbose to avoid a python 2.7ism
        local_image_unit_checksums = []
        for unit in local_image_units:
            local_image_unit_checksums.append(unit['image_checksum'])

        module_criteria = UnitAssociationCriteria(type_ids=[constants.IMAGE_TYPE_ID])
        existing_units_in_repo = conduit.get_units(criteria=module_criteria)


        _logger.info("local image units %s" % local_image_units)

        # find all images we know of in this repo
        _logger.info("local image units in our repo %s" % existing_units_in_repo)

        units_to_associate = []
        new_units = []
        for upstream_image in metadata:
            upstream_image.init_unit(conduit)
            if upstream_image.image_checksum in local_image_unit_checksums and \
              upstream_image._unit not in existing_units_in_repo:
               units_to_associate.append(upstream_image.unit_key)
            elif upstream_image.image_checksum not in local_image_unit_checksums:
                new_units.append(upstream_image)

        # create new associations of existing units
        conduit.associate_existing(constants.IMAGE_TYPE_ID,units_to_associate)

        # build up download list from new unit list
        for unit in new_units:
            image_url = urljoin(repo_url, unit.metadata['image_filename'])
            image_working_dest = os.path.join(self.get_working_dir(),
                                              unit.metadata['image_filename'])
            dl_request = request.DownloadRequest(image_url, image_working_dest)
            dl_request.data = unit
            self.downloads.append(dl_request)

        return len(self.downloads)

    def download_succeeded(self, report):
        """
        on image download success, copy file to content dir and create a unit

        :param report: report (unused here, just passed through to super)
        :type  report: report
        """
        unit = report.data
        image_working_src = os.path.join(self.get_working_dir(),
                                         unit.metadata['image_filename'])
        unit.init_unit(self.get_conduit()) 
        shutil.copyfile(image_working_src, unit.storage_path)
        unit.save_unit(self.get_conduit())
        # call super to handle report stuff
        super(GlanceImageDownloadStep, self).download_succeeded(report)

    def _get_metadata(self):
        config = self.get_config()
        image_metadata_path = os.path.join(self.get_working_dir(), models.ImageManifest.FILENAME)
        repo_url = config.get(importer_constants.KEY_FEED)
        with open(image_metadata_path) as image_metadata_file:
            metadata = models.ImageManifest(image_metadata_file, repo_url)

        return metadata
