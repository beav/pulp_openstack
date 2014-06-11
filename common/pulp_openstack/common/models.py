import os

from pulp_openstack.common import constants


class OpenstackImage(object):
    TYPE_ID = constants.IMAGE_TYPE_ID

    def __init__(self, image_checksum, image_size, image_filename):
        # TODO: add stuff like arch, image type, container type, etc
        """
        :param image_checksum:    MD5 sum
        :type  image_checksum:    basestring
        :param image_size:        size of file in bytes
        :type  image_size:        int
        :param image_filename:    filename for the image
        :type  image_filename:    basestring
        """
        self.image_checksum = image_checksum
        self.image_size = image_size
        self.image_filename = image_filename

    @property
    def unit_key(self):
        """
        :return:    unit key
        :rtype:     dict
        """
        return {
            'image_checksum': self.image_checksum,
            'image_size': self.image_size,
            'image_filename': self.image_filename
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

    def init_unit(self, conduit):
        """
        Use the given conduit's init_unit() call to initialize a unit, and
        store the unit as self._unit.

        :param conduit: The conduit to call init_unit() to get a Unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        relative_path_with_filename = os.path.join(self.relative_path(), self.image_filename)
        unit_key = {'image_size': self.image_size,
                    'image_checksum': self.image_checksum,
                    'image_filename': self.image_filename}
        metadata = {}
        # XXX: I think this wants relpath + filename, not just relpath
        self._unit = conduit.init_unit(self.TYPE_ID, unit_key, metadata, relative_path_with_filename)

    def validate(self):
        """
        Validate the checksum and filesize. This throws an exception if things aren't right.
        """
        pass

    @property
    def storage_path(self):
        """
        Return the storage path of the Unit that underlies this image.
        """
        return self._unit.storage_path
