import os

from pulp_openstack.common import constants


class OpenstackImage(object):
    TYPE_ID = constants.IMAGE_TYPE_ID

    def __init__(self, image_checksum, image_size):
        # TODO: add stuff like arch, image type, container type, etc
        """
        :param image_checksum:    MD5 sum
        :type  image_checksum:    basestring
        :param image_size:        size of file in bytes
        :type  image_size:        int
        """
        self.image_checksum = image_checksum
        self.image_size = image_size

    @property
    def unit_key(self):
        """
        :return:    unit key
        :rtype:     dict
        """
        return {
            'image_checksum': self.image_checksum,
            'image_size': self.image_size
        }

    @property
    def relative_path(self):
        """
        :return:    the relative path to where this image's directory should live
        :rtype:     basestring
        """
        return os.path.join(self.TYPE_ID, self.image_checksum)

    @property
    def unit_metadata(self):
        """
        :return:    a subset of the complete openstack metadata about this image,
                    including only what pulp_openstack cares about
        :rtype:     dict
        """
        # TODO: add stuff like arch, image type, container type, etc
        return {}
