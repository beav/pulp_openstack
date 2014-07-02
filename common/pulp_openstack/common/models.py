import logging
import os

import xml.etree.ElementTree as ET

from pulp_openstack.common import constants


logger = logging.getLogger(__name__)


class OpenstackImage(object):
    """
    A model that holds information about images
    """

    TYPE_ID = constants.IMAGE_TYPE_ID

    def __init__(self, image_checksum, properties):
        """
        :param image_checksum:    MD5 sum
        :type  image_checksum:    str
        :param properties:        a set of properties relevant to the image
        :type  properties:        dict
        """
        # assemble info for unit_key
        self.image_checksum = image_checksum
        self.metadata = properties

    @property
    def unit_key(self):
        """
        :return:    unit key
        :rtype:     dict
        """
        return {
            'image_checksum': self.image_checksum,
        }

    @property
    def size(self):
        """
        :return:    size of the image
        :rtype:     int
        """
        return int(self.metadata['image_size'])

    @property
    def relative_path(self):
        """
        :return:    the relative path to where this image's directory should live
        :rtype:     str
        """
        return self.image_checksum

    def init_unit(self, conduit):
        """
        Use the given conduit's init_unit() call to initialize a unit, and
        store the unit as self._unit.

        :param conduit: The conduit to call init_unit() to get a Unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        relative_path_with_filename = os.path.join(self.relative_path,
                                                   self.metadata['image_filename'])
        # this wants relpath + filename, not just relpath
        self._unit = conduit.init_unit(self.TYPE_ID, self.unit_key, self.metadata,
                                       relative_path_with_filename)

    def validate(self):
        """
        Validate the checksum and filesize. This throws an exception if things aren't right.
        """
        # TODO: Currently a no-op.
        pass

    @property
    def storage_path(self):
        """
        Return the storage path of the Unit that underlies this image.
        :return: storage path
        :rtype: string
        """
        return self._unit.storage_path

    @classmethod
    def from_unit(cls, unit):
        """
        Construct an image out of a unit.
        """
        return cls(unit.unit_key['image_checksum'], properties=unit.metadata)

    def save_unit(self, conduit):
        """
        Use the given conduit's save_unit() call to save self._unit.

        :param conduit: The conduit to call save_unit() with.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        conduit.save_unit(self._unit)


class ImageManifest(object):
    """
    This class provides an API that is a handy way to interact with an image
    manifest file. It automatically instantiates images out of the items found in the
    manifest.
    """
    # This is the filename that the manifest is published to
    FILENAME = '.image-metadata.xml'

    def __init__(self, manifest_file, repo_url):
        """
        Instantiate a new ImageManifest from the open manifest_file.

        :param manifest_file: An open file-like handle to a .image-manifest.xml file
        :type  manifest_file: An open file-like object
        :param repo_url:      The URL to the repository that this manifest came from. This is used
                              to determine a url attribute for each image in the manifest.
        :type  repo_url:      str
        """
        # Make sure we are reading from the beginning of the file
        manifest_file.seek(0)
        # Now let's process the manifest and return a list of resources that we'd like to download
        manifest_xml = manifest_file.read()
        logger.debug("image manifest: %s" % manifest_xml)

        self._images = []
        root = ET.fromstring(manifest_xml)
        for i in root:
            logger.debug("found image properties: %s" % i.attrib)
            image = OpenstackImage(i.attrib['image_checksum'], properties=i.attrib)
            self._images.append(image)

    def __iter__(self):
        """
        Return an iterator for the images in the manifest.
        """
        return iter(self._images)

    def __len__(self):
        """
        Return the number of images in the manifest.
        """
        return len(self._images)
