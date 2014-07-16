import unittest

from mock import Mock
from pulp.common.constants import REPO_NOTE_TYPE_KEY

from pulp_openstack.common import constants
from pulp_openstack.extensions.admin import cudl


class TestCreateOpenstackRepositoryCommand(unittest.TestCase):
    def test_default_notes(self):
        # make sure this value is set and is correct
        self.assertEqual(
            cudl.CreateOpenstackRepositoryCommand.default_notes.get(REPO_NOTE_TYPE_KEY),
            constants.REPO_NOTE_GLANCE)

    def test_importer_id(self):
        # this value is required to be set, so just make sure it's correct
        self.assertEqual(cudl.CreateOpenstackRepositoryCommand.IMPORTER_TYPE_ID,
                         constants.IMPORTER_TYPE_ID)

    def test_describe_distributors_basic(self):
        command = cudl.CreateOpenstackRepositoryCommand(Mock())
        result = command._describe_distributors({})
        self.assertEquals(result[0]["auto_publish"], True)

    def test_describe_distributors_override_auto_publish(self):
        command = cudl.CreateOpenstackRepositoryCommand(Mock())
        user_input = {
            'auto-publish': False
        }
        result = command._describe_distributors(user_input)
        self.assertEquals(result[0]["auto_publish"], False)

    def test_describe_distributors_check_protected(self):
        command = cudl.CreateOpenstackRepositoryCommand(Mock())
        user_input = {
            'protected': True
        }
        result = command._describe_distributors(user_input)
        for r in result:
            if r['distributor_id'] == 'openstack_web_distributor_name_cli':
                self.assertEquals(r["distributor_config"], {'protected': True})

    def test_describe_distributors_check_keystone_opts(self):
        command = cudl.CreateOpenstackRepositoryCommand(Mock())
        user_input = {
            'keystone-tenant': 'test-tenant',
            'keystone-username': 'test-username',
        }
        result = command._describe_distributors(user_input)
        for r in result:
            if r['distributor_id'] == 'openstack_glance_distributor_name_cli':
                self.assertEquals(r["distributor_config"], {'keystone-username': 'test-username',
                                                            'keystone-tenant': 'test-tenant'})

    def test_parse_importer_config(self):
        command = cudl.CreateOpenstackRepositoryCommand(Mock())
        result = command._parse_importer_config({'feed-url': 'http://example.com/'})
        print result
        self.assertEquals(result["feed"], 'http://example.com/')
