import unittest

import mock
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository

import data
from pulp_openstack.common import constants
from pulp_openstack.plugins.importers import importer
from pulp_openstack.plugins.importers.importer import OpenstackImageImporter


class TestBasics(unittest.TestCase):
    def test_metadata(self):
        metadata = OpenstackImageImporter.metadata()

        self.assertEqual(metadata['id'], constants.IMPORTER_TYPE_ID)
        self.assertEqual(metadata['types'], [constants.IMAGE_TYPE_ID])
        self.assertTrue(len(metadata['display_name']) > 0)

    @mock.patch('pulp.common.config.read_json_config')
    def test_entry_point(self, mock_read_json_config):
        cls, plugin_conf = importer.entry_point()
        self.assertEquals(cls.__name__, 'OpenstackImageImporter')


class TestImportUnits(unittest.TestCase):

    def setUp(self):
        self.unit_key = {'image_checksum': data.cirros_img_metadata['image_checksum']}
        self.source_repo = Repository('repo_source')
        self.dest_repo = Repository('repo_dest')
        self.conduit = mock.MagicMock()
        self.config = PluginCallConfiguration({}, {})

    def test_import_all(self):
        mock_unit = mock.Mock(unit_key={'image_checksum':
                                        '5a46e37274928bb39f84415e2ef61240'},
                              metadata={'min_ram': 1024})
        self.conduit.get_source_units.return_value = [mock_unit]
        result = OpenstackImageImporter().import_units(self.source_repo, self.dest_repo,
                                                       self.conduit, self.config)
        self.assertEquals(result, [mock_unit])
        self.conduit.associate_unit.assert_called_once_with(mock_unit)

    def test_import(self):
        mock_unit = mock.Mock(unit_key={'image_checksum':
                                        '5a46e37274928bb39f84415e2ef61240'},
                              metadata={'min_ram': 1024})
        result = OpenstackImageImporter().import_units(self.source_repo, self.dest_repo,
                                                       self.conduit, self.config, units=[mock_unit])
        self.assertEquals(result, [mock_unit])
        self.conduit.associate_unit.assert_called_once()


class TestUploadUnit(unittest.TestCase):

    @mock.patch('shutil.move')
    def test_upload(self, mock_move):
        unit_key = {'image_checksum': 'a_checksum'}
        metadata = {'min_ram': 1024, 'image_size': 100, 'image_filename': 'testfile.qcow2'}
        mock_conduit = mock.MagicMock()

        OpenstackImageImporter().upload_unit(None, None, unit_key, metadata,
                                             '/fake/file/path', mock_conduit, None)
        mock_conduit.save_unit.assert_called_once()

    @mock.patch('pulp_openstack.common.models.OpenstackImage.validate')
    @mock.patch('shutil.move')
    @mock.patch('os.remove')
    def test_upload_invalid_file(self, mock_remove, mock_move, mock_validate):
        unit_key = {'image_checksum': 'a_checksum'}
        metadata = {'min_ram': 1024,
                    'image_size': 100,
                    'image_filename': 'testfile.qcow2'}

        mock_conduit = mock.MagicMock()
        mock_validate.side_effect = ValueError('mock validation failure')

        OpenstackImageImporter().upload_unit(None, None, unit_key, metadata,
                                             '/fake/file/path', mock_conduit, None)
        mock_remove.remove.assert_called_once()


class TestSync(unittest.TestCase):

    def test_validate_config(self):
        config = {'feed': 'http://example.com/repo/'}
        mock_repo = mock.MagicMock()
        result = OpenstackImageImporter().validate_config(mock_repo, config)
        self.assertEquals(result, (True, ''))

    # this just tests that sync was called and does not test sync itself
    @mock.patch('pulp_openstack.plugins.importers.sync.ImageSyncRun')
    def test_sync_repo(self, mock_imagesyncrun):
        mock_config = mock.MagicMock()
        mock_conduit = mock.MagicMock()
        mock_repo = mock.MagicMock()
        OpenstackImageImporter().sync_repo(mock_repo, mock_conduit, mock_config)
        # assert called once with no args
        mock_imagesyncrun().perform_sync.assert_called_once_with()
