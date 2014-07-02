from gettext import gettext as _
from cStringIO import StringIO
from urlparse import urljoin
import logging

from nectar import listener, request
from nectar.config import DownloaderConfig
from nectar.downloaders.threaded import HTTPThreadedDownloader
from nectar.downloaders.local import LocalFileDownloader
from pulp.common.plugins import importer_constants
from pulp.common.util import encode_unicode
from pulp.plugins.conduits.mixins import UnitAssociationCriteria

from pulp.common.plugins.progress import SyncProgressReport
from pulp_openstack.common import constants
from pulp_openstack.common import models


logger = logging.getLogger(__name__)


class ImageSyncRun(listener.DownloadEventListener):
    """
    This class maintains state for a single repository sync (do not reuse it).
    We need to keep the state so that we can cancel a sync that is in progress. It
    subclasses DownloadEventListener so it can pass itself to the downloader
    library and receive the callbacks when downloads are complete.
    """

    def __init__(self, sync_conduit, config):
        """
        set up ImageSyncRun
        :param sync_conduit: sync conduit
        :type  sync_conduit: pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config: config
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        self.sync_conduit = sync_conduit
        # TODO: configure these
        self._remove_missing_units = False
        self._validate_downloads = False
        self._repo_url = encode_unicode(config.get(importer_constants.KEY_FEED))
        # The _repo_url must end in a trailing slash, because we will use
        # urljoin to determine the path to image metadata file later
        if self._repo_url[-1] != '/':
            self._repo_url = self._repo_url + '/'

        # Cast our config parameters to the correct types and use them to build a Downloader
        max_speed = config.get(importer_constants.KEY_MAX_SPEED)
        if max_speed is not None:
            max_speed = float(max_speed)
        max_downloads = config.get(importer_constants.KEY_MAX_DOWNLOADS)
        if max_downloads is not None:
            max_downloads = int(max_downloads)
        else:
            max_downloads = constants.CONFIG_MAX_DOWNLOADS_DEFAULT
        ssl_validation = config.get_boolean(importer_constants.KEY_SSL_VALIDATION)
        ssl_validation = ssl_validation if ssl_validation is not None \
            else constants.CONFIG_VALIDATE_DEFAULT
        downloader_config = {
            'max_speed': max_speed,
            'max_concurrent': max_downloads,
            'ssl_client_cert': config.get(importer_constants.KEY_SSL_CLIENT_CERT),
            'ssl_client_key': config.get(importer_constants.KEY_SSL_CLIENT_KEY),
            'ssl_ca_cert': config.get(importer_constants.KEY_SSL_CA_CERT),
            'ssl_validation': ssl_validation,
            'proxy_url': config.get(importer_constants.KEY_PROXY_HOST),
            'proxy_port': config.get(importer_constants.KEY_PROXY_PORT),
            'proxy_username': config.get(importer_constants.KEY_PROXY_USER),
            'proxy_password': config.get(importer_constants.KEY_PROXY_PASS)}
        downloader_config = DownloaderConfig(**downloader_config)

        # We will pass self as the event_listener, so that we can receive the
        # callbacks in this class
        if self._repo_url.lower().startswith('file'):
            self.downloader = LocalFileDownloader(downloader_config, self)
        else:
            self.downloader = HTTPThreadedDownloader(downloader_config, self)
        self.progress_report = SyncProgressReport(sync_conduit)

    def cancel_sync(self):
        """
        This method will cancel a sync that is in progress.
        """
        # We used to support sync cancellation, but the current downloader
        # implementation does not support it and so for now we will just pass
        self.progress_report.state = self.progress_report.STATE_CANCELLED
        self.downloader.cancel()

    def download_failed(self, report):
        """
        This is the callback that we will get from the downloader library when any individual
        download fails.
        :param report: report
        :type  report: report
        """
        # If we have a download failure during the manifest phase, we should set the report to
        # failed for that phase.
        msg = _('Failed to download %(url)s: %(error_msg)s.')
        msg = msg % {'url': report.url, 'error_msg': report.error_msg}
        logger.error(msg)
        if self.progress_report.state == self.progress_report.STATE_MANIFEST_IN_PROGRESS:
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            self.progress_report.error_message = report.error_report
        elif self.progress_report.state == self.progress_report.STATE_FILES_IN_PROGRESS:
            image = report.data
            self.progress_report.add_failed_image(image, report.error_report)
        self.progress_report.update_progress()

    def download_progress(self, report):
        """
        We will get notified from time to time about some bytes we've
        downloaded. We can update our progress report with this information so the
        client can see the progress.

        :param report: The report of the file we are downloading
        :type  report: nectar.report.DownloadReport
        """
        if self.progress_report.state == self.progress_report.STATE_FILES_IN_PROGRESS:
            image = report.data
            additional_bytes_downloaded = report.bytes_downloaded - image.bytes_downloaded
            self.progress_report.finished_bytes += additional_bytes_downloaded
            image.bytes_downloaded = report.bytes_downloaded
            self.progress_report.update_progress()

    def download_succeeded(self, report):
        """
        This is the callback that we will get from the downloader library when
        it succeeds in downloading a file. This method will check to see if we are in
        the image downloading stage, and if we are, it will add the new image
        to the database.

        :param report: The report of the file we downloaded
        :type  report: nectar.report.DownloadReport
        """
        # If we are in the files stage, then this must be one of our files
        if self.progress_report.state == self.progress_report.STATE_FILES_IN_PROGRESS:
            # This will update our bytes downloaded
            self.download_progress(report)
            image = report.data
            try:
                if self._validate_downloads:
                    image.validate()
                image.save_unit(self.sync_conduit)
                # We can drop this file from the url --> file map
                self.progress_report.num_files_finished += 1
                self.progress_report.update_progress()
            except ValueError:
                self.download_failed(report)

    def perform_sync(self):
        """
        Perform the sync operation according to the config, and return a report.
        The sync progress will be reported through the sync_conduit.

        :return:             The sync report
        :rtype:              pulp.plugins.model.SyncReport
        """
        # Get the manifest and download the Images that we are missing
        self.progress_report.state = self.progress_report.STATE_MANIFEST_IN_PROGRESS
        try:
            manifest = self._download_manifest()
        except (IOError, ValueError):
            # The IOError will happen if the file can't be retrieved at all, and the ValueError will
            # happen if the image metadata file isn't in the expected format.
            return self.progress_report.build_final_report()

        # Go get them filez
        self.progress_report.state = self.progress_report.STATE_FILES_IN_PROGRESS
        local_missing_images, remote_missing_images = self._filter_missing_images(manifest)
        self._download_images(local_missing_images)
        if self._remove_missing_units:
            self._remove_units(remote_missing_images)

        # Report that we are finished. Note that setting the
        # state to STATE_FILES_COMPLETE will automatically set the state to
        # STATE_FILES_FAILED if the progress report has collected any errors.
        # See the progress_report's _set_state() method
        # for the implementation of this logic.
        self.progress_report.state = self.progress_report.STATE_COMPLETE
        report = self.progress_report.build_final_report()
        return report

    def _download_images(self, manifest):
        """
        Given a list of model objects, downloads their data to disk.


        :param manifest: The manifest containing a list of images we want to download.
        :type  manifest: list
        """
        self.progress_report.total_bytes = 0
        self.progress_report.num_files = len(manifest)
        # For each image in the manifest, we need to determine a relative path
        # where we want it to be stored, and initialize the Unit that will
        # represent it
        for image in manifest:
            image.init_unit(self.sync_conduit)
            image.url = urljoin(self._repo_url, image.metadata['image_filename'])
            image.bytes_downloaded = 0
            # Set the total bytes onto the report
            self.progress_report.total_bytes += image.size
        self.progress_report.update_progress()
        # We need to build a list of DownloadRequests
        download_requests = \
            [request.DownloadRequest(image.url, image.storage_path, image) for image in manifest]
        self.downloader.download(download_requests)

    def _filter_missing_images(self, manifest):
        """
        Use the sync_conduit and the manifest to determine which images are at
        the feed_url that are not in our local store, as well as which images are in
        our local store that are not available at the feed_url. Return a 2-tuple with
        this information. The first element of the tuple will be a list of image
        objects that represent the missing images. The second element will be a list of
        Units that represent the images we have in our local store that weren't found
        at the feed_url.

        :param manifest: An ImageManifest describing the images that are available at the
                         feed_url that we are synchronizing with
        :type  manifest: pulp_rpm.plugins.db.models.ImageManifest
        :return:         A 2-tuple. The first element of the tuple is a list of
                         Images that we should retrieve from the feed_url. The second element of the
                         tuple is a list of Units that represent the images that we have in our
                         local repo that were not found in the remote repo.
        :rtype:          tuple
        """
        def _unit_key_str(image):
            """
            Return a simple string representation of the unit key of the Image.

            :param image: The Image for which we want a unit key string representation
            :type  image: pulp_openstack.common.models.OpenstackImage
            """
            return '%s' % image.image_checksum

        module_criteria = UnitAssociationCriteria(type_ids=[constants.IMAGE_TYPE_ID])
        existing_units = self.sync_conduit.get_units(criteria=module_criteria)

        available_images_by_key = dict([(_unit_key_str(image), image) for image in manifest])
        existing_units_by_key = dict([(_unit_key_str(models.OpenstackImage.from_unit(unit)), unit)
                                      for unit in existing_units])

        existing_unit_keys = \
            set([_unit_key_str(models.OpenstackImage.from_unit(unit)) for unit in existing_units])
        available_image_keys = set([_unit_key_str(image) for image in manifest])

        local_missing_image_keys = list(available_image_keys - existing_unit_keys)
        local_missing_images = [available_images_by_key[k] for k in local_missing_image_keys]
        remote_missing_unit_keys = list(existing_unit_keys - available_image_keys)
        remote_missing_units = [existing_units_by_key[k] for k in remote_missing_unit_keys]

        return local_missing_images, remote_missing_units

    def _remove_units(self, units):
        """
        Use the sync_conduit's remove_unit call for each unit in units.

        :param units: List of pulp.plugins.model.Units that we want to remove from the repository
        :type  units: list
        """
        for unit in units:
            self.sync_conduit.remove_unit(unit)

    def _download_manifest(self):
        """
        Download the manifest file, and process it to return an ImageManifest.

        :return: manifest of available images
        :rtype:  pulp_openstack.common.models.ImageManifest
        """
        manifest_url = urljoin(self._repo_url, models.ImageManifest.FILENAME)
        manifest_destination = StringIO()
        manifest_request = request.DownloadRequest(manifest_url, manifest_destination)
        self.downloader.download([manifest_request])
        # We can inspect the report status to see if we had an error when retrieving the manifest.
        if self.progress_report.state == self.progress_report.STATE_MANIFEST_FAILED:
            raise IOError(_("Could not retrieve %(url)s") % {'url': manifest_url})

        manifest_destination.seek(0)
        try:
            manifest = models.ImageManifest(manifest_destination, self._repo_url)
            for i in manifest:
                logger.info("image: %s" % i)
        except ValueError:
            self.progress_report.error_message = _('The manifest file was not in the '
                                                   'expected format.')
            self.progress_report.state = self.progress_report.STATE_MANIFEST_FAILED
            raise ValueError(self.progress_report.error_message)

        return manifest
