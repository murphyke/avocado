import logging
import os
import re
import sys
from django.test import TestCase
from django.test.utils import override_settings
from django.core import management
from avocado.models import DataField, DataContext, DataView


__all__ = ('CommandsTestCase',)


class MockLoggingHandler(logging.Handler):
    """
    Mock logging handler to check for expected logs.

    This mock logging handler is from Gustavo's answer on this thread:
        http://stackoverflow.com/questions/899067/how-should-i-verify-a-log-message-when-testing-python-code-under-nose/1049375#1049375
    """

    def __init__(self, *args, **kwargs):
        self.reset()
        logging.Handler.__init__(self, *args, **kwargs)

    def emit(self, record):
        self.messages[record.levelname.lower()].append(record.getMessage())

    def reset(self):
        self.messages = {
            'debug': [],
            'info': [],
            'warning': [],
            'error': [],
            'critical': [],
        }


class CommandsTestCase(TestCase):
    fixtures = ['employee_data.json', 'legacy.json']

    def setUp(self):
        self.stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def tearDown(self):
        sys.stdout = self.stdout

    def test_subcommands(self):
        management.call_command('avocado', 'init', 'tests')
        management.call_command('avocado', 'cache', 'tests')
        management.call_command('avocado', 'check', output='none')
        management.call_command('avocado', 'history', cull=True)

        # Before updating the data, the data_version be at the default value 1
        self.assertEqual(DataField.objects.filter()[:1].get().data_version, 1)

        management.call_command('avocado', 'data', 'tests', incr_version=True)

        # After calling the data command with the incr_version argument
        # set to True, we should see an incremented data_version of 2
        self.assertEqual(DataField.objects.filter()[:1].get().data_version, 2)

        management.call_command('avocado', 'data', 'tests')

        # Confirm that calling the data command without the optional
        # incr_version argument does not cause the data_version field
        # to get incremented.
        self.assertEqual(DataField.objects.filter()[:1].get().data_version, 2)

    def test_empty_fixture_dir(self):
        from avocado.conf import settings

        # Create a mock log handler so we can peep the log messages
        log_handler = MockLoggingHandler()
        logging.getLogger().addHandler(log_handler)

        # Initialize patterns to match desired log messages against
        fixture_pattern = re.compile('Created fixture \d{4}_avocado_metadata')
        migration_pattern = re.compile('Created migration \d{4}_avocado_metadata_migration.py')

        original_fixture_dir = settings.METADATA_FIXTURE_DIR
        settings.METADATA_FIXTURE_DIR = '/tmp/dir1/dir2/'
        management.call_command('avocado', 'migration')
        settings.METADATA_FIXTURE_DIR = original_fixture_dir

        # Get a list of just the info messages and verify the length before
        # checking the individual messages.
        info_messages = log_handler.messages['info']
        self.assertEqual(len(info_messages), 4)

        # Make sure the individual log messages match the expected output or
        # at the very least the expected pattern of the output.
        self.assertIsNotNone(fixture_pattern.match(info_messages[0]))
        self.assertIsNotNone(fixture_pattern.match(info_messages[1]))
        self.assertIsNotNone(migration_pattern.match(info_messages[2]))
        self.assertEqual(info_messages[3], 'Faked migrations up to the current one')

    def test_legacy(self):
        from avocado.models import DataField
        management.call_command('avocado', 'legacy', no_input=True)
        fields = DataField.objects.all()

        # 2/3 have been migrated
        self.assertEqual(len(fields), 2)

        f1 = DataField.objects.get_by_natural_key('tests', 'title', 'name')
        # Turned on the enumerable flag
        self.assertTrue(f1.enumerable)
        self.assertFalse(f1.published)

        f1 = DataField.objects.get_by_natural_key('tests', 'title', 'salary')
        # Turned off the enumerable flag
        self.assertFalse(f1.enumerable)
        self.assertFalse(f1.enumerable)
