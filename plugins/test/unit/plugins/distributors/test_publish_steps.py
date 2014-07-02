import os
import shutil
import tempfile
import unittest

from mock import Mock, patch

from pulp.devel.unit.util import touch

from pulp.plugins.conduits.repo_publish import RepoPublishConduit
from pulp.plugins.config import PluginCallConfiguration
from pulp.plugins.model import Repository
from pulp.plugins.util.publish_step import PublishStep

from pulp_openstack.common import constants
from pulp_openstack.plugins.distributors import publish_steps


class TestPublishImagesStep(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.working_directory = os.path.join(self.temp_dir, 'working')
        self.publish_directory = os.path.join(self.temp_dir, 'publish')
        self.content_directory = os.path.join(self.temp_dir, 'content')
        os.makedirs(self.working_directory)
        os.makedirs(self.publish_directory)
        os.makedirs(self.content_directory)
        repo = Repository('foo_repo_id', working_dir=self.working_directory)
        config = PluginCallConfiguration(None, None)
        conduit = RepoPublishConduit(repo.id, 'foo_repo')
        self.parent = PublishStep('test-step', repo, conduit, config)

    def test_process_unit(self):
        step = publish_steps.PublishImagesStep()
        fake_image_filename = 'fake-zero-byte-image.qcow2'
        touch(os.path.join(self.content_directory, fake_image_filename))

        unit = Mock(unit_key={'image_checksum': 'd41d8cd98f00b204e9800998ecf8427e'},
                    storage_path=os.path.join(self.content_directory, fake_image_filename),
                    metadata={'image_container_format': 'mock_fmt',
                              'image_disk_format': 'mock_fmt',
                              'image_size': 10000,
                              'image_name': 'mock unit',
                              'image_min_disk': 4096,
                              'image_min_ram': 1024})
        step.get_working_dir = Mock(return_value=self.publish_directory)
        step.process_unit(unit)
        # verify symlink
        expected_symlink = os.path.join(self.publish_directory, 'web', fake_image_filename)
        self.assertTrue(os.path.exists(expected_symlink))

    def test_finalize(self):
        step = publish_steps.PublishImagesStep()
        step.parent = self.parent
        step.finalize()
        # verify xml file was created
        expected_content = '<pulp_image_manifest version="1" />'
        with open(os.path.join(self.working_directory, 'web', '.image-metadata.xml')) as f:
            self.assertEquals(f.readline(), expected_content)

    def test_finalize_metadata_exists(self):
        step = publish_steps.PublishImagesStep()
        step.parent = self.parent
        # test that if the directory already exists, we keep going
        os.mkdir(os.path.join(self.working_directory, 'web'))
        step.finalize()
        # verify xml file was created
        expected_content = '<pulp_image_manifest version="1" />'
        with open(os.path.join(self.working_directory, 'web', '.image-metadata.xml')) as f:
            self.assertEquals(f.readline(), expected_content)

    def test_finalize_with_images(self):
        step = publish_steps.PublishImagesStep()
        step.parent = self.parent
        repo_metadata_fragment_1 = {'checksum': '123456',
                                    'container_format': 'bare',
                                    'disk_format': 'qcow2',
                                    'filename': 'foo.qcow2',
                                    'min_disk': '102400',
                                    'min_ram': '2048',
                                    'name': 'Foo Image Name',
                                    'size': '10000'}
        repo_metadata_fragment_2 = {'checksum': 'abcdef',
                                    'container_format': 'bare',
                                    'disk_format': 'qcow2',
                                    'filename': 'bar.qcow2',
                                    'min_disk': '204800',
                                    'min_ram': '4096',
                                    'name': 'Bar Image Name',
                                    'size': '20000'}

        step.repo_metadata = [repo_metadata_fragment_1, repo_metadata_fragment_2]
        step.finalize()
        # verify xml file was created
        expected_content = '<pulp_image_manifest version="1"><image checksum="123456"' \
                           ' container_format="bare" disk_format="qcow2" filename="foo.qcow2"' \
                           ' min_disk="102400" min_ram="2048" name="Foo Image Name"' \
                           ' size="10000" /><image checksum="abcdef" container_format="bare"' \
                           ' disk_format="qcow2" filename="bar.qcow2" min_disk="204800"' \
                           ' min_ram="4096" name="Bar Image Name" size="20000"' \
                           ' /></pulp_image_manifest>'
        with open(os.path.join(self.working_directory, 'web', '.image-metadata.xml')) as f:
            self.assertEquals(f.readline(), expected_content)


class TestWebPublisher(unittest.TestCase):

    def setUp(self):
        self.working_directory = tempfile.mkdtemp()
        self.publish_dir = os.path.join(self.working_directory, 'publish')
        self.master_dir = os.path.join(self.working_directory, 'master')
        self.working_temp = os.path.join(self.working_directory, 'work')
        self.repo = Mock(id='foo', working_dir=self.working_temp)

    def tearDown(self):
        shutil.rmtree(self.working_directory)

    @patch('pulp_openstack.plugins.distributors.publish_steps.AtomicDirectoryPublishStep')
    @patch('pulp_openstack.plugins.distributors.publish_steps.PublishImagesStep')
    def test_init(self, mock_images_step, mock_web_publish_step):
        mock_conduit = Mock()
        mock_config = {
            constants.CONFIG_KEY_GLANCE_PUBLISH_DIRECTORY: self.publish_dir
        }
        publisher = publish_steps.WebPublisher(self.repo, mock_conduit, mock_config)
        self.assertEquals(publisher.children, [mock_images_step.return_value,
                                               mock_web_publish_step.return_value])
