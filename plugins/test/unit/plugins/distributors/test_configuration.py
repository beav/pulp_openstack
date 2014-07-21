import os
import shutil
import tempfile
import unittest

from mock import Mock

from pulp.devel.unit.server.util import assert_validation_exception
from pulp.plugins.config import PluginCallConfiguration

from pulp_openstack.common import constants, error_codes
from pulp_openstack.plugins.distributors import configuration


class TestValidateConfig(unittest.TestCase):

    def test_configuration_protected_true(self):
        config = PluginCallConfiguration({
            constants.CONFIG_KEY_PROTECTED: True
        }, {})

        self.assertEquals((True, None), configuration.validate_config(config))

    def test_configuration_protected_false_str(self):
        config = PluginCallConfiguration({
            constants.CONFIG_KEY_PROTECTED: 'false'
        }, {})

        self.assertEquals((True, None), configuration.validate_config(config))

    def test_configuration_protected_bad_str(self):
        config = PluginCallConfiguration({
            constants.CONFIG_KEY_PROTECTED: 'apple'
        }, {})
        assert_validation_exception(configuration.validate_config,
                                    [error_codes.OST1004], config)


class TestConfigurationGetters(unittest.TestCase):

    def setUp(self):
        self.working_directory = tempfile.mkdtemp()
        self.publish_dir = os.path.join(self.working_directory, 'publish')
        self.repo_working = os.path.join(self.working_directory, 'work')

        self.repo = Mock(id='foo', working_dir=self.repo_working)
        self.config = {
            constants.CONFIG_KEY_GLANCE_PUBLISH_DIRECTORY: self.publish_dir
        }

    def tearDown(self):
        shutil.rmtree(self.working_directory)

    def test_get_root_publish_directory(self):
        directory = configuration.get_root_publish_directory(self.config)
        self.assertEquals(directory, self.publish_dir)

    def test_get_master_publish_dir(self):
        directory = configuration.get_master_publish_dir(self.repo, self.config)
        self.assertEquals(directory, os.path.join(self.publish_dir, 'master', self.repo.id))

    def test_get_web_publish_dir(self):
        directory = configuration.get_web_publish_dir(self.repo, self.config)
        self.assertEquals(directory, os.path.join(self.publish_dir, 'web', self.repo.id))

    def test_get_repo_relative_path(self):
        directory = configuration.get_repo_relative_path(self.repo, self.config)
        self.assertEquals(directory, self.repo.id)
