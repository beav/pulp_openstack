import os
# NEED TO VERIFY
import shutil
import tempfile
import unittest

from mock import Mock, MagicMock, patch
from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
from pulp.plugins.distributor import Distributor

from pulp_openstack.common import constants
from pulp_openstack.plugins.distributors.distributor_web import OpenstackImageWebDistributor
from pulp_openstack.plugins.distributors.distributor_web import entry_point


class TestEntryPoint(unittest.TestCase):
    def test_returns_importer(self):
        distributor, config = entry_point()

        self.assertTrue(issubclass(distributor, Distributor))

    def test_returns_config(self):
        distributor, config = entry_point()

        # make sure it's at least the correct type
        self.assertTrue(isinstance(config, dict))


class TestBasics(unittest.TestCase):

    def setUp(self):
        self.distributor = OpenstackImageWebDistributor()
        self.working_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.working_dir, ignore_errors=True)

    def test_metadata(self):
        metadata = OpenstackImageWebDistributor.metadata()

        self.assertEqual(metadata['id'], constants.DISTRIBUTOR_WEB_TYPE_ID)
        self.assertEqual(metadata['types'], [constants.IMAGE_TYPE_ID])
        self.assertTrue(len(metadata['display_name']) > 0)

    @patch('pulp_openstack.plugins.distributors.distributor_web.configuration.validate_config')
    def test_validate_config(self, mock_validate):
        value = self.distributor.validate_config(Mock(), 'foo', Mock())
        mock_validate.assert_called_once_with('foo')
        self.assertEquals(value, mock_validate.return_value)

    def test_distributor_removed(self):
        # TODO: fix
        pass

    @patch('pulp_openstack.plugins.distributors.distributor_web.configuration.get_app_publish_dir')
    @patch('pulp_openstack.plugins.distributors.distributor_web.configuration.'
           'get_master_publish_dir')
    @patch('pulp_openstack.plugins.distributors.distributor_web.configuration.get_web_publish_dir')
    def test_distributor_removed_files_missing(self, mock_web, mock_master, mock_app):
        mock_app.return_value = os.path.join(self.working_dir)
        mock_web.return_value = os.path.join(self.working_dir, 'web')
        mock_master.return_value = os.path.join(self.working_dir, 'master')
        working_dir = os.path.join(self.working_dir, 'working')
        repo = Mock(id='bar', working_dir=working_dir)
        config = {}
        self.distributor.distributor_removed(repo, config)
        self.assertEquals(0, len(os.listdir(self.working_dir)))

    @patch('pulp_openstack.plugins.distributors.distributor_web.WebPublisher')
    def test_publish_repo(self, mock_publisher):
        repo = Repository('test')
        config = PluginCallConfiguration(None, None)
        conduit = RepoPublishConduit(repo.id, 'foo_repo')
        self.distributor.publish_repo(repo, conduit, config)

        mock_publisher.return_value.assert_called_once()

    def test_cancel_publish_repo(self):
        self.distributor._publisher = MagicMock()
        self.distributor.cancel_publish_repo()
        self.assertTrue(self.distributor.canceled)

        self.distributor._publisher.cancel.assert_called_once()
