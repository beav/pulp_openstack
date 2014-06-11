from gettext import gettext as _

from pulp.client.commands import options
from pulp.client.commands.criteria import DisplayUnitAssociationsCommand
from pulp.client.commands.unit import UnitCopyCommand, UnitRemoveCommand

from pulp_openstack.common import constants


DESC_COPY = _('copies images from one repository into another')
DESC_REMOVE = _('remove images from a repository')
DESC_SEARCH = _('search for images in a repository')

MODULE_ID_TEMPLATE = '%(image_id)s'


def get_formatter_for_type(type_id):
    """
    Return a method that takes one argument (a unit) and formats a short string
    to be used as the output for the unit_remove command

    :param type_id: The type of the unit for which a formatter is needed
    :type type_id: str
    :raises ValueError: if the method does not recognize the type_id
    """

    if type_id != constants.IMAGE_TYPE_ID:
        raise ValueError(_("The openstack image formatter can not process %s units.") % type_id)

    return lambda x: MODULE_ID_TEMPLATE % x


class ImageCopyCommand(UnitCopyCommand):

    def __init__(self, context, name='copy', description=DESC_COPY):
        super(ImageCopyCommand, self).__init__(context, name=name, description=description,
                                               method=self.run, type_id=constants.IMAGE_TYPE_ID)

    @staticmethod
    def get_formatter_for_type(type_id):
        """
        Returns a method that can be used to format the unit key of a openstack image
        for display purposes

        :param type_id: the type_id of the unit key to get a formatter for
        :type type_id: str
        :return: function
        """
        return get_formatter_for_type(type_id)


class ImageRemoveCommand(UnitRemoveCommand):
    """
    Class for executing unit remove commands for openstack image units
    """

    def __init__(self, context, name='remove', description=DESC_REMOVE):
        UnitRemoveCommand.__init__(self, context, name=name, description=description,
                                   type_id=constants.IMAGE_TYPE_ID)

    @staticmethod
    def get_formatter_for_type(type_id):
        """
        Returns a method that can be used to format the unit key for display
        purposes

        :param type_id: the type_id of the unit key to get a formatter for
        :type type_id: str
        :return: function
        """
        return get_formatter_for_type(type_id)


class ImageSearchCommand(DisplayUnitAssociationsCommand):
    def __init__(self, context):
        super(ImageSearchCommand, self).__init__(self.run, name='images', description=DESC_SEARCH)
        self.context = context
        self.prompt = context.prompt

    def run(self, **kwargs):
        """
        Print a list of all the images matching the search parameters in kwargs

        :param kwargs: the search parameters for finding openstack images
        :type kwargs: dict
        """
        # Get the list of images
        repo_id = kwargs.pop(options.OPTION_REPO_ID.keyword)
        kwargs['type_ids'] = [constants.IMAGE_TYPE_ID]
        images = self.context.server.repo_unit.search(repo_id, **kwargs).response_body

        self.prompt.render_document_list(images)
