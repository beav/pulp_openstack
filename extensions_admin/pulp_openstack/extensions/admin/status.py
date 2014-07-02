from pulp.client.commands.repo.sync_publish import SyncStatusRenderer

from pulp_openstack.common import constants
from pulp.common.plugins.progress import SyncProgressReport


class ImageStatusRenderer(SyncStatusRenderer):
    """
    This is based heavily on the ISO status renderer
    """

    def __init__(self, context):
        """
        Initialize status renderer.

        See super for details
        """

        super(self.__class__, self).__init__(context)

        self._sync_files_bar = self.prompt.create_progress_bar()

        # Let's have our status renderer track the same state transitions are the SyncProgressReport
        self._sync_state = SyncProgressReport.STATE_NOT_STARTED

    def display_report(self, progress_report):
        """
        Bet you couldn't guess that this method displays the progress_report.

        :param progress_report: The progress report that we want to display to the user
        :type  progress_report: pulp_openstack.extensions.admin.progress
        """
        if constants.IMPORTER_TYPE_ID in progress_report:
            sync_report = SyncProgressReport.from_progress_report(
                progress_report[constants.IMPORTER_TYPE_ID])
            self._display_manifest_sync_report(sync_report, "image manifest")
            self._display_sync_report(sync_report, "images")

            if sync_report.state == sync_report.STATE_CANCELED:
                self.prompt.render_failure_message('The download was cancelled.', tag='cancelled')
