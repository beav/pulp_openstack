import unittest
from mock import Mock, MagicMock

from pulp_openstack.common import models


class TestImageBasics(unittest.TestCase):
    def test_init_info(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_size': 10000,
                                       'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024})

        self.assertEqual(image.image_checksum, '70924d6fa4b2d745185fa4660703a5c0')

    def test_unit_key(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})

        self.assertEqual(image.unit_key, {'image_checksum': '70924d6fa4b2d745185fa4660703a5c0'})

    def test_relative_path(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})

        self.assertEqual(image.relative_path, '70924d6fa4b2d745185fa4660703a5c0')

    def test_metadata(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})
        self.assertEqual(image.metadata, {'min_ram': 1024, 'name': 'test image',
                                          'image_filename': 'a_filename.img', 'image_size': 10000})

    def test_size(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})
        self.assertEqual(image.size, 10000)

    def test_from_unit(self):
        unit = MagicMock()
        unit.unit_key = {'image_checksum': '123456abcdef'}

        image = models.OpenstackImage.from_unit(unit)

        self.assertEqual(image.image_checksum, '123456abcdef')

    def test_save_unit(self):
        mock_conduit = MagicMock()
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})
        image.init_unit(mock_conduit)
        image.save_unit(mock_conduit)
        mock_conduit.save_unit.assert_called_once_with(image._unit)

    def test_metadata_add_props(self):
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'image_filename': 'a_filename.img',
                                       'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000})
        self.assertEqual(image.metadata, {'name': 'test image', 'min_ram': 1024,
                                          'image_filename': 'a_filename.img', 'image_size': 10000})

    def test_init_unit(self):
        mock_conduit = Mock()
        image = models.OpenstackImage('70924d6fa4b2d745185fa4660703a5c0',
                                      {'name': 'test image', 'min_ram': 1024,
                                       'image_size': 10000,
                                       'image_filename': 'a_filename.img'})
        image.init_unit(mock_conduit)
        expected_call = ('openstack_image', {'image_checksum': '70924d6fa4b2d745185fa4660703a5c0'},
                         {'min_ram': 1024, 'image_filename': 'a_filename.img',
                          'name': 'test image', 'image_size': 10000},
                         '70924d6fa4b2d745185fa4660703a5c0/a_filename.img')
        mock_conduit.init_unit.assert_called_once_with(*expected_call)


class TestImageManifestBasics(unittest.TestCase):

    def test_init(self):
        mock_file = MagicMock()
        # an empty manifest
        mock_file.read.return_value = '<pulp_image_manifest version="1" />'
        manifest = models.ImageManifest(mock_file, 'http://example.com/somerepo/')
        self.assertEqual(len(manifest), 0)

    def test_init_with_images(self):
        mock_file = MagicMock()
        # a manifest with data. Sorry for the lack of newlines, that is how the
        # actual file is written:)
        mock_file.read.return_value = '<pulp_image_manifest version="1"><image image_checksum='\
                                      '"64d7c1cd2b6f60c92c14662941cb7913" image_container_form'\
                                      'at="foo" image_disk_format="foo" image_filename="cirros'\
                                      '-0.3.2-x86_64-disk.img" image_min_disk="None" image_min'\
                                      '_ram="1024" image_name="test4" image_size="13167616"/><'\
                                      '/pulp_image_manifest>'
        manifest = models.ImageManifest(mock_file, 'http://example.com/somerepo/')
        self.assertEqual(len(manifest), 1)
        # verify the iterator was called when looping
        was_called = False
        for image in manifest:
            was_called = True
        self.assertTrue(was_called)
