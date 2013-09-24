import os
import time
from django.contrib.auth.models import User
from django.core import management
from django.db import models
from django.test import TestCase, TransactionTestCase
from django.test.utils import override_settings
from avocado.core import utils
from avocado.core.loader import Registry, AlreadyRegistered
from avocado.core.paginator import BufferedPaginator

__all__ = ('RegistryTestCase', 'BufferedPaginatorTestCase',
    'CachedMethodTestCase', 'CacheProxyTestCase', 'CacheManagerTestCase',
    'BackupTestCase', 'EmailBasedUserTestCase')

class RegistryTestCase(TestCase):
    def setUp(self):
        class A(object): pass
        class B(object): pass
        self.A = A
        self.B = B
        self.r = Registry(register_instance=False)

    def test_register(self):
        self.r.register(self.B)
        self.r.register(self.A)
        self.assertEqual(self.r.choices, [('A', 'A'), ('B', 'B')])

    def test_unregister(self):
        self.r.register(self.A)
        self.assertEqual(self.r.choices, [('A', 'A')])
        self.r.unregister(self.A)
        self.assertEqual(self.r.choices, [])

    def test_already(self):
        self.r.register(self.A)
        self.assertRaises(AlreadyRegistered, self.r.register, self.A)

    def test_default(self):
        class C(object): pass
        self.r.register(C, default=True)
        self.assertEqual(self.r['Default'], C)

        class D(object): pass
        self.r.register(D, default=True)
        self.assertEqual(self.r['Default'], D)


class BufferedPaginatorTestCase(TestCase):
    def test_base(self):
        kwargs = {
            'count': 100,
            'offset': 0,
            'buf_size': 10,
            'object_list': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            'per_page': 2
        }

        bp = BufferedPaginator(**kwargs)

        self.assertEqual(bp.num_pages, 50)
        self.assertEqual(bp.cached_page_indices(), (1, 6))
        self.assertEqual(bp.cached_pages(), 5)

        self.assertTrue(bp.page(2).in_cache())
        self.assertFalse(bp.page(6).in_cache())

    def test_offset(self):
        kwargs = {
            'count': 100,
            'offset': 40,
            'buf_size': 10,
            'object_list': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            'per_page': 2
        }

        bp = BufferedPaginator(**kwargs)

        self.assertEqual(bp.num_pages, 50)
        self.assertEqual(bp.cached_page_indices(), (21, 26))
        self.assertEqual(bp.cached_pages(), 5)

        self.assertFalse(bp.page(20).in_cache())
        self.assertTrue(bp.page(21).in_cache())
        self.assertFalse(bp.page(26).in_cache())

        # try as a negative offset
        kwargs['offset'] = -60

        bp = BufferedPaginator(**kwargs)

        self.assertEqual(bp.num_pages, 50)
        self.assertEqual(bp.cached_page_indices(), (21, 26))
        self.assertEqual(bp.cached_pages(), 5)

        self.assertFalse(bp.page(20).in_cache())
        self.assertTrue(bp.page(21).in_cache())
        self.assertFalse(bp.page(26).in_cache())

    def test_partial(self):
        kwargs = {
            'count': 20,
            'offset': 0,
            'buf_size': 10,
            'object_list': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            'per_page': 40
        }

        bp = BufferedPaginator(**kwargs)

        self.assertEqual(bp.num_pages, 1)
        self.assertEqual(bp.cached_page_indices(), (1, 2))
        self.assertEqual(bp.cached_pages(), 1)

        p1 = bp.page(1)
        self.assertTrue(p1.in_cache())
        self.assertEqual((p1.start_index(), p1.end_index()), (1, 20))
        self.assertEqual(p1.object_list, kwargs['object_list'])

        kwargs['offset'] = 10

        bp = BufferedPaginator(**kwargs)

        self.assertEqual(bp.num_pages, 1)
        self.assertEqual(bp.cached_page_indices(), (0, 0))
        self.assertEqual(bp.cached_pages(), 0)

    def test_overlap(self):
        kwargs = {
            'count': 100,
            'offset': 50,
            'buf_size': 10,
            'object_list': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            'per_page': 2
        }

        bp = BufferedPaginator(**kwargs)

        # use paginator's buf_size
        self.assertEqual(bp.get_overlap(45), (True, (45, 5), (None, None)))
        self.assertEqual(bp.get_overlap(47), (True, (47, 3), (None, None)))
        self.assertEqual(bp.get_overlap(55), (True, (None, None), (61, 5)))
        self.assertEqual(bp.get_overlap(52), (True, (None, None), (61, 2)))
        self.assertEqual(bp.get_overlap(20), (False, (20, 10), (None, None)))
        self.assertEqual(bp.get_overlap(70), (False, (70, 10), (None, None)))

        # explicit buf_size
        self.assertEqual(bp.get_overlap(47, 14), (True, (47, 3), (61, 1)))
        self.assertEqual(bp.get_overlap(20, 100), (True, (20, 30), (61, 60)))
        self.assertEqual(bp.get_overlap(55, 12), (True, (None, None), (61, 7)))
        self.assertEqual(bp.get_overlap(20, 8), (False, (20, 8), (None, None)))
        self.assertEqual(bp.get_overlap(70, 3), (False, (70, 3), (None, None)))


class CacheProxyTestCase(TestCase):
    class ComplexNumber(models.Model):
        def __init__(self):
            from avocado.core.cache.model import CacheProxy
            from avocado.core.cache import instance_cache_key

            self.id = 100

            self.cache_proxy = CacheProxy(func=self.as_string,
                version='get_version', timeout=2,
                key_func=instance_cache_key)
            self.cache_proxy.func_self = self

        def get_version(self, label=None):
            return 1

        def as_string(self, *args):
            return "2+3i"

    @override_settings(AVOCADO_DATA_CACHE_ENABLED=True)
    def test(self):
        c = self.ComplexNumber()

        # Should not be cached available or cached initialization
        self.assertIsNone(c.cache_proxy.get())
        self.assertFalse(c.cache_proxy.cached())

        self.assertEqual(c.cache_proxy.get_or_set(), '2+3i')

        # Should be cached now
        self.assertTrue(c.cache_proxy.cached())
        self.assertEqual(c.cache_proxy.get(), '2+3i')

        time.sleep(2)

        # Make sure the value expired
        self.assertIsNone(c.cache_proxy.get())
        self.assertFalse(c.cache_proxy.cached())

    def test_cache_disabled(self):
        c = self.ComplexNumber()
        c.cache_proxy.func_self = None

        self.assertIsNone(c.cache_proxy.cache_key)
        self.assertIsNone(c.cache_proxy.get())
        self.assertIsNone(c.cache_proxy.get_or_set())
        self.assertIsNone(c.cache_proxy.flush())
        self.assertFalse(c.cache_proxy.cached())


class CacheManagerTestCase(TestCase):
    @override_settings(AVOCADO_DATA_CACHE_ENABLED=True)
    def test(self):
        from .models import Foo

        self.assertEqual(Foo.objects.get_query_set().count(), 0)

        for i in range(10):
            f = Foo()
            f.save()

        self.assertEqual(Foo.objects.get_query_set().count(), 10)


class CachedMethodTestCase(TestCase):
    @override_settings(AVOCADO_DATA_CACHE_ENABLED=True)
    def test(self):
        from .models import Foo

        f = Foo()

        # Not cached upon initialization
        self.assertFalse(f.callable_versioned.cached())
        self.assertFalse(f.default_versioned.cached())
        self.assertFalse(f.versioned.cached())
        self.assertFalse(f.unversioned.cached())

        self.assertEqual(f.default_versioned(), [4])
        self.assertEqual(f.callable_versioned(), [3])
        self.assertEqual(f.versioned(), [2])
        self.assertEqual(f.unversioned(), [1])

        self.assertTrue(f.default_versioned.cached())
        self.assertTrue(f.callable_versioned.cached())
        self.assertTrue(f.versioned.cached())
        self.assertTrue(f.unversioned.cached())

        # Time passes..
        time.sleep(2)

        # default_versioned was created using the default arguments so it should
        # never expire. All the rest had a timeout.
        self.assertTrue(f.default_versioned.cached())
        self.assertFalse(f.callable_versioned.cached())
        self.assertFalse(f.versioned.cached())
        self.assertFalse(f.unversioned.cached())

        self.assertEqual(f.callable_versioned(), [3])
        self.assertEqual(f.versioned(), [2])
        self.assertEqual(f.unversioned(), [1])

        self.assertTrue(f.callable_versioned.cached())
        self.assertTrue(f.versioned.cached())
        self.assertTrue(f.unversioned.cached())

        f.default_versioned.flush()
        f.callable_versioned.flush()
        f.versioned.flush()
        f.unversioned.flush()

        self.assertFalse(f.default_versioned.cached())
        self.assertFalse(f.callable_versioned.cached())
        self.assertFalse(f.versioned.cached())
        self.assertFalse(f.unversioned.cached())


@override_settings(SOUTH_TESTS_MIGRATE=True)
class BackupTestCase(TransactionTestCase):
    def test_fixture_dir(self):
        from avocado.core import backup
        self.assertEqual(backup.get_fixture_dir(), os.path.join(os.path.dirname(__file__), 'fixtures'))

    def test_safe_load_tmp(self):
        from avocado.core import backup
        from avocado.models import DataField

        management.call_command('avocado', 'init', 'tests')
        self.assertEqual(DataField.objects.count(), 18)

        backup_path = backup.safe_load('0001_avocado_metadata')

        self.assertTrue(os.path.exists(backup_path))
        self.assertEqual(DataField.objects.count(), 3)
        os.remove(backup_path)

    def test_safe_load(self):
        from avocado.core import backup
        from avocado.models import DataField

        management.call_command('avocado', 'init', 'tests')
        self.assertEqual(DataField.objects.count(), 18)

        backup_path = backup.safe_load('0001_avocado_metadata',
            backup_path='backup.json')

        self.assertTrue(os.path.exists('backup.json'))
        self.assertEqual(DataField.objects.count(), 3)
        os.remove(backup_path)

    def test_fixture_filenames(self):
        from avocado.core import backup
        filenames = backup._fixture_filenames(backup.get_fixture_dir())
        self.assertEqual(filenames, ['0001_avocado_metadata.json'])

    def test_next_fixture_name(self):
        from avocado.core import backup
        from avocado.conf import settings
        filename = backup.next_fixture_name(settings.METADATA_FIXTURE_SUFFIX,
            backup.get_fixture_dir())
        self.assertEqual(filename, '0002_avocado_metadata')

    def test_migration_call(self):
        from avocado.core import backup
        management.call_command('avocado', 'migration')
        migration_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        self.assertTrue(os.path.exists(os.path.join(migration_dir, '0003_avocado_metadata_migration.py')))
        os.remove(os.path.join(migration_dir, '0003_avocado_metadata_migration.py'))
        os.remove(os.path.join(backup.get_fixture_dir(), '0002_avocado_metadata.json'))

    def test_migration(self):
        management.call_command('migrate', 'core')


class EmailBasedUserTestCase(TestCase):
    email = 'email@email.com'

    def test_create_user(self):
        # Make sure we are starting with the anticipated number of users.
        self.assertEqual(User.objects.count(), 1)

        user = utils.create_email_based_user(self.email)

        self.assertEqual(User.objects.count(), 2)

        # Make sure the user we got back has the correct email set and that
        # they are not active.
        self.assertEqual(user.email, self.email)
        self.assertFalse(user.is_active)
