from gettext import gettext as _

import logging

from urlparse import urljoin
from cStringIO import StringIO

from nectar import listener, request
from nectar.config import DownloaderConfig
from nectar.downloaders.threaded import HTTPThreadedDownloader

from pulp.common.plugins import importer_constants
from pulp.plugins.util.sync_step import SyncStep, UnitSyncStep

from pulp_openstack.common import constants, models

_logger = logging.getLogger(__name__)


class SyncImages(SyncStep):
    """
    Openstack image sync class that syncs images via http
    """

    def __init__(self, repo, sync_conduit, config):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param sync_conduit: Conduit providing access to relative Pulp functionality
        :type  sync_conduit: tbd
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        super(SyncImages, self).__init__(constants.SYNC_STEP, repo, sync_conduit, config)

        self.add_child(DownloadManifestStep(repo, sync_conduit, config))
        self.add_child(SyncImagesStep())


class DownloadManifestStep(SyncStep, listener.DownloadEventListener):
    """
    Openstack sync class to grab manifests
    """

    def __init__(self, repo, sync_conduit, config):
        """
        initialize manifest downloader

        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param sync_conduit: Conduit providing access to relative Pulp functionality
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        super(DownloadManifestStep, self).__init__(constants.SYNC_STEP_MANIFEST, repo,
                                                   sync_conduit, config)
        self.description = _('Downloading image repo manifest for %s' % repo.id)

    def initialize(self):
        """
        This step is the one that actually downloads the manifest.
        """
        _logger.debug("downloading manifest for repo %s" % self.get_repo())
        conduit = self.get_conduit()
        config = self.get_config()
        downloader = HTTPThreadedDownloader(DownloaderConfig(), self)

        repo_url = config.get(importer_constants.KEY_FEED)
        manifest_url = urljoin(repo_url, models.ImageManifest.FILENAME)

        manifest_destination = StringIO()
        manifest_request = request.DownloadRequest(manifest_url, manifest_destination)
        downloader.download([manifest_request])
        manifest_destination.seek(0)

        # if there are any errors, just let them raise normally
        manifest = models.ImageManifest(manifest_destination, repo_url)
        conduit._images = manifest
        _logger.info("manifest: %s" % manifest_destination.getvalue())


class SyncImagesStep(UnitSyncStep, listener.DownloadEventListener):
    """
    Sync Images
    """

    def __init__(self):
        """
        Initialize sync.
        """
        super(SyncImagesStep, self).__init__(constants.SYNC_STEP_IMAGES, constants.IMAGE_TYPE_ID)
        self.context = None
        self.description = _('Syncing images')

        self.downloader = HTTPThreadedDownloader(DownloaderConfig(), self)

    def get_unit_generator(self):
        """
        return a generator with units we want to process

        :return: generator of units
        :rtype: a generator
        """
        conduit = self.get_conduit()
        return (x for x in conduit._images)

    def _get_total(self):
        """
        return count of how many units we are going to work with

        :return: total unit count
        :rtype: int
        """
        conduit = self.get_conduit()
        return len(conduit._images)

    def process_unit(self, unit):
        """
        download the file and create the unit

        :param unit: The unit to process
        :type  unit: pulp_openstack.common.models.OpenstackImage
        """
        config = self.get_config()
        conduit = self.get_conduit()

        unit.init_unit(conduit)
        repo_url = config.get(importer_constants.KEY_FEED)
        unit.url = urljoin(repo_url, unit.metadata['image_filename'])

        unit_request = request.DownloadRequest(unit.url, unit.storage_path, unit)
        self.downloader.download([unit_request])

    # from listener.DownloadEventListener
    def download_succeeded(self, report):
        """
        This is the callback that we will get from the downloader library when any individual
        download succeeds.

        :param report: report
        :type  report: report
        """
        unit = report.data
        conduit = self.get_conduit()
        unit.save_unit(conduit)
        _logger.debug("unit %s saved" % unit)
