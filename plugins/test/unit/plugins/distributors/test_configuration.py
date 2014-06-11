import os
# NEED TO VERIFY
import shutil
import tempfile
import unittest

from mock import Mock, patch

from pulp.devel.unit.server.util import assert_validation_exception
from pulp.plugins.config import PluginCallConfiguration

from pulp_openstack.common import constants, error_codes
from pulp_openstack.plugins.distributors import configuration


class TestValidateConfig(unittest.TestCase):

    def test_server_url_fully_qualified(self):
        config = {
            constants.CONFIG_KEY_REDIRECT_URL: 'http://www.pulpproject.org/foo'
        }
        self.assertEquals((True, None), configuration.validate_config(config))

    def test_server_url_fully_qualified_with_port(self):
        config = {
            constants.CONFIG_KEY_REDIRECT_URL: 'http://www.pulpproject.org:440/foo'
        }
        self.assertEquals((True, None), configuration.validate_config(config))

    def test_server_url_empty(self):
        config = {
            constants.CONFIG_KEY_REDIRECT_URL: ''
        }
        # This is valid as the default server should be used

        self.assertEquals((True, None), configuration.validate_config(config))

    def test_server_url_missing_host_and_path(self):
        config = {
            constants.CONFIG_KEY_REDIRECT_URL: 'http://'
        }
        assert_validation_exception(configuration.validate_config,
                                    [error_codes.GLA1002,
                                     error_codes.GLA1003], config)

    def test_server_url_missing_scheme(self):
        config = {
            constants.CONFIG_KEY_REDIRECT_URL: 'www.pulpproject.org/foo'
        }
        assert_validation_exception(configuration.validate_config,
                                    [error_codes.GLA1001,
                                     error_codes.GLA1002], config)

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
                                    [error_codes.GLA1004], config)


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

    def test_get_redirect_url_from_config(self):
        sample_url = 'http://www.pulpproject.org/'
        conduit = Mock(repo_id=sample_url)
        url = configuration.get_redirect_url({constants.CONFIG_KEY_REDIRECT_URL: sample_url},
                                             conduit)
        self.assertEquals(sample_url, url)

    def test_get_redirect_url_from_config_trailing_slash(self):
        sample_url = 'http://www.pulpproject.org'
        conduit = Mock(repo_id=sample_url)
        url = configuration.get_redirect_url({constants.CONFIG_KEY_REDIRECT_URL: sample_url},
                                             conduit)
        self.assertEquals(sample_url + '/', url)

    @patch('pulp_openstack.plugins.distributors.configuration.server_config')
    def test_get_redirect_url_generated(self, mock_server_config):
        mock_server_config.get.return_value = 'www.foo.bar'
        computed_result = 'https://www.foo.bar/pulp/openstack/baz/'
        self.assertEquals(computed_result, configuration.get_redirect_url({},
                                                                          Mock(id='baz')))
