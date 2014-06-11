import unittest
# NEED TO VERIFY

import mock
from pulp.client.commands.repo.cudl import CreateRepositoryCommand, DeleteRepositoryCommand
from pulp.client.commands.repo.cudl import UpdateRepositoryCommand
from pulp.client.commands.repo.sync_publish import PublishStatusCommand, RunPublishRepositoryCommand
from pulp.client.commands.repo.upload import UploadCommand
from pulp.client.extensions.core import PulpCli

from pulp_openstack.extensions.admin import pulp_cli
from pulp_openstack.extensions.admin import images
from pulp_openstack.extensions.admin.repo_list import ListOpenstackRepositoriesCommand


class TestInitialize(unittest.TestCase):
    def test_structure(self):
        context = mock.MagicMock()
        context.config = {
            'filesystem': {'upload_working_dir': '/a/b/c'},
            'output': {'poll_frequency_in_seconds': 3}
        }
        context.cli = PulpCli(context)

        # create the tree of commands and sections
        pulp_cli.initialize(context)

        # verify that sections exist and have the right commands
        openstack_section = context.cli.root_section.subsections['openstack']

        repo_section = openstack_section.subsections['repo']
        self.assertTrue(isinstance(repo_section.commands['create'], CreateRepositoryCommand))
        self.assertTrue(isinstance(repo_section.commands['delete'], DeleteRepositoryCommand))
        self.assertTrue(isinstance(repo_section.commands['update'], UpdateRepositoryCommand))
        self.assertTrue(isinstance(repo_section.commands['list'], ListOpenstackRepositoriesCommand))
        self.assertTrue(isinstance(repo_section.commands['images'], images.ImageSearchCommand))
        self.assertTrue(isinstance(repo_section.commands['copy'], images.ImageCopyCommand))
        self.assertTrue(isinstance(repo_section.commands['remove'], images.ImageRemoveCommand))

        upload_section = repo_section.subsections['uploads']
        self.assertTrue(isinstance(upload_section.commands['upload'], UploadCommand))

        section = repo_section.subsections['publish']
        self.assertTrue(isinstance(section.commands['status'], PublishStatusCommand))
        self.assertTrue(isinstance(section.commands['run'], RunPublishRepositoryCommand))
