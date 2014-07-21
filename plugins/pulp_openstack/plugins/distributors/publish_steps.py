from gettext import gettext as _

import logging
import os
import xml.etree.cElementTree as ET

from pulp.plugins.util.publish_step import PublishStep, UnitPublishStep, \
    AtomicDirectoryPublishStep

from pulp_openstack.common import constants, models
from pulp_openstack.plugins.distributors import configuration

_logger = logging.getLogger(__name__)


class WebPublisher(PublishStep):
    """
    Openstack Image Web publisher class that is responsible for the actual publishing
    of a openstack image repository via a web server
    """

    def __init__(self, repo, publish_conduit, config):
        """
        :param repo: Pulp managed Yum repository
        :type  repo: pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config: Pulp configuration for the distributor
        :type  config: pulp.plugins.config.PluginCallConfiguration
        """
        super(WebPublisher, self).__init__(constants.PUBLISH_STEP_WEB_PUBLISHER,
                                           repo, publish_conduit, config)

        publish_dir = configuration.get_web_publish_dir(repo, config)
        self.web_working_dir = os.path.join(self.get_working_dir(), 'web')
        master_publish_dir = configuration.get_master_publish_dir(repo, config)
        atomic_publish_step = AtomicDirectoryPublishStep(self.get_working_dir(),
                                                         [('web', publish_dir)],
                                                         master_publish_dir,
                                                         step_type=constants.PUBLISH_STEP_OVER_HTTP)
        atomic_publish_step.description = _('Making files available via web.')
        self.add_child(PublishImagesStep())
        self.add_child(atomic_publish_step)


class PublishImagesStep(UnitPublishStep):
    """
    Publish Images
    """

    def __init__(self):
        """
        Initialize publisher.
        """
        super(PublishImagesStep, self).__init__(constants.PUBLISH_STEP_IMAGES,
                                                constants.IMAGE_TYPE_ID)
        self.context = None
        self.description = _('Publishing Image Files.')
        self.repo_metadata = []

    def process_unit(self, unit):
        """
        Link the unit to the image content directory

        :param unit: The unit to process
        :type  unit: pulp_openstack.common.models.OpenstackImage
        """
        # note: we do not use the image checksum in the published directory path
        target_base = os.path.join(self.get_web_directory())
        _logger.debug("linking %s to %s" % (unit.storage_path,
                                            os.path.join(target_base,
                                                         os.path.basename(unit.storage_path))))
        PublishStep._create_symlink(unit.storage_path,
                                    os.path.join(target_base, os.path.basename(unit.storage_path)))

        # create repo metadata fragment and add to list
        repo_metadata_fragment = {'image_filename': os.path.basename(unit.storage_path),
                                  'image_checksum': unit.unit_key['image_checksum'],
                                  'image_container_format': unit.metadata['image_container_format'],
                                  'image_disk_format': unit.metadata['image_disk_format'],
                                  'image_size': str(unit.metadata['image_size']),
                                  'image_name': unit.metadata['image_name'],
                                  'image_min_disk': str(unit.metadata['image_min_disk']),
                                  'image_min_ram': str(unit.metadata['image_min_ram'])}

        self.repo_metadata.append(repo_metadata_fragment)

    def finalize(self):
        """
        Close & finalize each the metadata context
        """
        repo_metadata_filename = os.path.join(self.get_web_directory(),
                                              models.ImageManifest.FILENAME)
        self._write_metadata_file(self.repo_metadata, repo_metadata_filename)

    def _write_metadata_file(self, repo_metadata, repo_metadata_filename):
        """
        write out metadata for image repo

        :param repo_metadata: list of metadata fragments
        :type  repo_metadata: list of dicts
        :param repo_metadata_filename: repo metadata filename
        :type  repo_metadata_filename: str
        """
        _logger.debug("writing metadata for %s units to %s" % (len(repo_metadata),
                                                               repo_metadata_filename))
        root = ET.Element("pulp_image_manifest", {'version': '1'})
        for rm in repo_metadata:
            element = ET.SubElement(root, 'image')
            for e in rm:
                element.attrib[e] = str(rm[e])

        tree = ET.ElementTree(root)
        tree.write(repo_metadata_filename)

    def get_web_directory(self):
        """
        Get the directory where the files published to the web have been linked
        :return: path to web directory
        :rtype: str
        """
        return os.path.join(self.get_working_dir(), 'web')
