from copy import deepcopy
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from django.test import TestCase
from django.core import management
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models.query import ValuesListQuerySet
from guardian.shortcuts import assign
from avocado.models import (DataField, DataConcept, DataConceptField,
                            DataContext, DataView, DataQuery, DataCategory)
from ...models import Employee


class ModelInstanceCacheTestCase(TestCase):
    fixtures = ['models.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)
        self.is_manager = DataField.objects.get_by_natural_key('tests',
                                                               'employee',
                                                               'is_manager')

    def test_datafield_cache(self):
        cache.clear()

        pk = self.is_manager.pk
        # New query, object is fetched from cache
        queryset = DataField.objects.filter(pk=pk)
        self.assertEqual(queryset._result_cache, None)

        self.is_manager.save()

        queryset = DataField.objects.filter(pk=pk)
        # Without this len test, the _result_cache will not be populated due to
        # the inherent laziness of the filter method.
        self.assertGreater(len(queryset), 0)
        self.assertEqual(queryset._result_cache[0].pk, pk)


class DataFieldTestCase(TestCase):
    fixtures = ['models.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)
        self.is_manager = DataField.objects.get_by_natural_key('tests',
                                                               'employee',
                                                               'is_manager')
        self.salary = DataField.objects.get_by_natural_key('tests', 'title',
                                                           'salary')
        self.first_name = DataField.objects.get_by_natural_key('tests',
                                                               'employee',
                                                               'first_name')

    def test_boolean(self):
        self.assertTrue(self.is_manager.model)
        self.assertTrue(self.is_manager.field)
        self.assertEqual(self.is_manager.simple_type, 'boolean')
        self.assertEqual(self.is_manager.nullable, True)

    def test_integer(self):
        self.assertTrue(self.salary.model)
        self.assertTrue(self.salary.field)
        self.assertEqual(self.salary.simple_type, 'number')
        self.assertEqual(self.salary.nullable, True)

    def test_string(self):
        self.assertTrue(self.first_name.model)
        self.assertTrue(self.first_name.field)
        self.assertEqual(self.first_name.simple_type, 'string')
        self.assertEqual(self.first_name.nullable, False)


class DataFieldChoicesQuerySetTestCase(TestCase):
    """
    Test DataField.choices_queryset
    """
    fixtures = ['employee_data.json', 'month_data.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)

    def test_regular_field(self):
        for obj in DataField.objects.all():
            print '{app}.{mod}.{fld}'.format(app=obj.app_name,
                                             mod=obj.model_name,
                                             fld=obj.field_name)
        first_name_field = DataField.objects.get_by_natural_key('tests',
                                                                'employee',
                                                                'first_name')
        qs = first_name_field.choices_queryset()
        self.assertIsInstance(qs, ValuesListQuerySet)
        expected = [(u'Aaron', u'Aaron'),
                    (u'Eric', u'Eric'),
                    (u'Erick', u'Erick'),
                    (u'Erin', u'Erin'),
                    (u'Mel', u'Mel'),
                    (u'Zac', u'Zac')]
        self.assertEqual(expected, list(qs))

    def test_lexicon_field(self):
        from ...models import Month
        month_field = DataField.objects.get_by_natural_key('tests', 'month',
                                                           'id')
        self.assertTrue(month_field.lexicon)
        qs = month_field.choices_queryset()
        self.assertIsInstance(qs, ValuesListQuerySet)
        expected = [(1, u'January'),
                    (2, u'February'),
                    (3, u'March'),
                    (4, u'April'),
                    (5, u'May'),
                    (6, u'June'),
                    (7, u'July'),
                    (8, u'August'),
                    (9, u'September'),
                    (10, u'October'),
                    (11, u'November'),
                    (12, u'December')]
        self.assertEqual(expected, list(qs))
        # Now check ordering
        for obj in Month.objects.all():
            obj.order = 12 - obj.order
            obj.save()
        qs = month_field.choices_queryset()
        self.assertIsInstance(qs, ValuesListQuerySet)
        expected = [(12, u'December'),
                    (11, u'November'),
                    (10, u'October'),
                    (9, u'September'),
                    (8, u'August'),
                    (7, u'July'),
                    (6, u'June'),
                    (5, u'May'),
                    (4, u'April'),
                    (3, u'March'),
                    (2, u'February'),
                    (1, u'January')]
        self.assertEqual(expected, list(qs))

    def test_objectset_field(self):
        from ...models import RecordSet
        [RecordSet(name=u'Set {0}'.format(i)).save() for i in xrange(10)]
        f = DataField(app_name='tests', model_name='recordset',
                      field_name='id')
        qs = f.choices_queryset()
        self.assertIsInstance(qs, ValuesListQuerySet)
        expected = [(1, u'Set 0'),
                    (2, u'Set 1'),
                    (3, u'Set 2'),
                    (4, u'Set 3'),
                    (5, u'Set 4'),
                    (6, u'Set 5'),
                    (7, u'Set 6'),
                    (8, u'Set 7'),
                    (9, u'Set 8'),
                    (10, u'Set 9')]
        self.assertEqual(expected, list(qs))


class DataFieldManagerTestCase(TestCase):
    fixtures = ['models.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)
        self.is_manager = DataField.objects.get_by_natural_key('tests',
                                                               'employee',
                                                               'is_manager')

    def test_published(self):
        # Published, not specific to any user
        self.assertEqual([x.pk for x in DataField.objects.published()], [])

        self.is_manager.published = True
        self.is_manager.save()

        # Now published, it will appear
        self.assertEqual([x.pk for x in DataField.objects.published()], [7])

        user1 = User.objects.create_user('user1', 'user1')
        user2 = User.objects.create_user('user2', 'user2')
        assign('avocado.view_datafield', user1, self.is_manager)

        # Now restrict the fields that are published and are assigned to users
        self.assertEqual([x.pk for x in DataField.objects.published(user1)],
                         [7])
        # `user2` is not assigned
        self.assertEqual([x.pk for x in DataField.objects.published(user2)],
                         [])


class DataConceptTestCase(TestCase):
    fixtures = ['models.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)

    def test_format(self):
        name_field = DataField.objects.get_by_natural_key('tests', 'title',
                                                          'name')
        salary_field = DataField.objects.get_by_natural_key('tests', 'title',
                                                            'salary')
        boss_field = DataField.objects.get_by_natural_key('tests', 'title',
                                                          'boss')

        concept = DataConcept(name='Title')
        concept.save()

        DataConceptField(concept=concept, field=name_field, order=1).save()
        DataConceptField(concept=concept, field=salary_field, order=2).save()
        DataConceptField(concept=concept, field=boss_field, order=3).save()

        values = ['CEO', 100000, True]

        self.assertEqual(concept.format(values),
                         OrderedDict([
                             (u'name', u'CEO'),
                             (u'salary', 100000),
                             (u'boss', True)
                         ]))

        self.assertEqual(concept._formatter_cache[0], None)

        from avocado.formatters import Formatter, registry as formatters

        class HtmlFormatter(Formatter):
            def to_html(self, values, **context):
                fvalues = self(values, preferred_formats=['string'])
                return OrderedDict({
                    'profile': '<span>' + '</span><span>'.join(
                        fvalues.values()) + '</span>'
                })

            to_html.process_multiple = True

        formatters.register(HtmlFormatter, 'HTML')
        concept.formatter_name = 'HTML'

        profile_value = u'<span>CEO</span><span>100000</span><span>True</span>'
        self.assertEqual(concept.format(values, preferred_formats=['html']),
                         OrderedDict({'profile': profile_value}))


class DataConceptManagerTestCase(TestCase):
    fixtures = ['models.json']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)
        self.is_manager = DataField.objects.get_by_natural_key('tests',
                                                               'employee',
                                                               'is_manager')
        self.salary = DataField.objects.get_by_natural_key('tests', 'title',
                                                           'salary')
        DataCategory(published=False).save()
        self.category = DataCategory.objects.get(pk=1)

    def test_published(self):
        concept = DataConcept(published=True)
        concept.save()
        DataConceptField(concept=concept, field=self.is_manager).save()
        DataConceptField(concept=concept, field=self.salary).save()

        self.assertEqual([x.pk for x in DataConcept.objects.published()], [])

        self.is_manager.published = True
        self.is_manager.save()
        self.salary.published = True
        self.salary.save()

        # Now published, it will appear
        self.assertEqual([x.pk for x in DataConcept.objects.published()], [1])

        # Set the category to be an unpublished category and it should no
        # longer appear.
        concept.category = self.category
        concept.save()
        self.assertEqual([x.pk for x in DataConcept.objects.published()], [])

        # Publish the category and the concept should appear again
        self.category.published = True
        self.category.save()
        self.assertEqual([x.pk for x in DataConcept.objects.published()], [1])

        user1 = User.objects.create_user('user1', 'user1')

        # Nothing since user1 cannot view either datafield
        self.assertEqual([x.pk for x in DataConcept.objects.published(user1)],
                         [])

        assign('avocado.view_datafield', user1, self.is_manager)
        # Still nothing since user1 has no permission for salary
        self.assertEqual([x.pk for x in DataConcept.objects.published(user1)],
                         [])

        assign('avocado.view_datafield', user1, self.salary)
        # Now user1 can see the concept
        self.assertEqual([x.pk for x in DataConcept.objects.published(user1)],
                         [1])

        user2 = User.objects.create_user('user2', 'user2')

        # `user2` is not assigned
        self.assertEqual([x.pk for x in DataConcept.objects.published(user2)],
                         [])

        # Remove the fields from the concept and it should no longer appear
        # as published.
        DataConceptField.objects.filter(concept=concept).delete()
        self.assertEqual([x.pk for x in DataConcept.objects.published()], [])


class DataContextTestCase(TestCase):
    def test_init(self):
        json = {'field': 'tests.title.salary', 'operator': 'gt',
                'value': '1000'}
        cxt = DataContext(json)
        self.assertEqual(cxt.json, json)

    def test_clean(self):
        # Save a default template
        cxt = DataContext(template=True, default=True)
        cxt.save()

        # Save new template (not default)
        cxt2 = DataContext(template=True)
        cxt2.save()

        # Try changing it to default
        cxt2.default = True
        self.assertRaises(ValidationError, cxt2.save)

        cxt.save()


class DataViewTestCase(TestCase):
    def test_init(self):
        json = {'columns': []}
        view = DataView(json)
        self.assertEqual(view.json, json)

    def test_clean(self):
        # Save a default template
        view = DataView(template=True, default=True)
        view.save()

        # Save new template (not default)
        view2 = DataView(template=True)
        view2.save()

        # Try changing it to default
        view2.default = True
        self.assertRaises(ValidationError, view2.save)

        view.save()


class DataQueryTestCase(TestCase):
    fixtures = ['query.json']
    existing_email = 'existing@email.com'
    emails = [existing_email, 'new1@email.com', 'new2@email.com',
              'new3@email.com']

    def setUp(self):
        management.call_command('avocado', 'init', 'tests', publish=False,
                                concepts=False, quiet=True)
        f1 = DataField.objects.get(pk=1)
        f2 = DataField.objects.get(pk=2)

        c1 = DataConcept()
        c1.save()

        DataConceptField(concept=c1, field=f1).save()
        DataConceptField(concept=c1, field=f2).save()

    def test_init(self):
        json = {
            'context': {'field': 'tests.title.salary', 'operator': 'gt',
                        'value': '1000'},
            'view': {'columns': []}
        }

        query = DataQuery(json)
        self.assertEqual(query.context_json, json['context'])
        self.assertEqual(query.view_json, json['view'])

        # Test the json of the DataQuery properties too
        self.assertEqual(query.context.json, json['context'])
        self.assertEqual(query.view.json, json['view'])

        self.assertEqual(query.json, json)

    def test_multiple_json_values(self):
        json = {
            'context': {'field': 'tests.title.salary', 'operator': 'gt',
                        'value': '1000'},
            'view': {'columns': []}
        }
        context_json = {
            'context_json': {'field': 'tests.title.salary', 'operator': 'gt',
                             'value': '1000'},
        }
        view_json = {
            'view_json': {'columns': []}
        }

        self.assertRaises(TypeError, DataQuery, json, **context_json)
        self.assertRaises(TypeError, DataQuery, json, **view_json)

    def test_validate(self):
        attrs = {
            'context': {
                'field': 'tests.title.name',
                'operator': 'exact',
                'value': 'CEO',
                'language': 'Name is CEO'
            },
            'view': {
                'columns': [1],
            }
        }

        exp_attrs = deepcopy(attrs)
        exp_attrs['view'] = [{'concept': 1}]

        self.assertEqual(DataQuery.validate(deepcopy(attrs), tree=Employee),
                         exp_attrs)

    def test_parse(self):
        attrs = {
            'context': {
                'type': 'and',
                'children': [{
                    'field': 'tests.title.name',
                    'operator': 'exact',
                    'value': 'CEO',
                }]
            },
            'view': {
                'ordering': [(1, 'desc')]
            }
        }

        query = DataQuery(attrs)
        node = query.parse(tree=Employee)
        self.assertEqual(str(node.datacontext_node.condition),
                         "(AND: ('title__name__exact', u'CEO'))")
        self.assertEqual(str(node.dataview_node.ordering), "[(1, 'desc')]")

    def test_apply(self):
        attrs = {
            'context': {
                'field': 'tests.title.boss',
                'operator': 'exact',
                'value': True
            },
            'view': {
                'columns': [1],
            }
        }
        query = DataQuery(attrs)

        expected_sql = (
            'SELECT DISTINCT "tests_employee"."id", "tests_office"."location",'
            ' "tests_title"."name" '
            'FROM "tests_employee" INNER JOIN "tests_title" '
            'ON ("tests_employee"."title_id" = "tests_title"."id") '
            'INNER JOIN "tests_office" '
            'ON ("tests_employee"."office_id" = "tests_office"."id") '
            'WHERE "tests_title"."boss" = True '
        )
        self.assertEqual(unicode(query.apply(tree=Employee).query),
                         expected_sql)

        query = DataQuery({'view': {'ordering': [(1, 'desc')]}})
        queryset = Employee.objects.all().distinct()
        expected_sql = (
            'SELECT DISTINCT "tests_employee"."id", "tests_office"."location",'
            ' "tests_title"."name" '
            'FROM "tests_employee" INNER JOIN "tests_office" '
            'ON ("tests_employee"."office_id" = "tests_office"."id") '
            'LEFT OUTER JOIN "tests_title" '
            'ON ("tests_employee"."title_id" = "tests_title"."id") '
            'ORDER BY "tests_office"."location" DESC, "tests_title"."name" '
            'DESC'
        )
        self.assertEqual(unicode(query.apply(queryset=queryset).query),
                         expected_sql)

    def test_clean(self):
        # Save default template
        query = DataQuery(template=True, default=True)
        query.save()

        # Save new template (not default)
        query2 = DataQuery(template=True)
        query2.save()

        # Try changing the second query to the default
        query2.default = True
        self.assertRaises(ValidationError, query2.save)

        query.save()

    def test_add_shared_user(self):
        # Make sure we are starting with the anticipated number of users.
        self.assertEqual(User.objects.count(), 1)

        # Assign an email to the existing user
        User.objects.all().update(email=self.existing_email)

        query = DataQuery(template=True, default=True)
        query.save()

        self.assertEqual(query.shared_users.count(), 0)

        [query.share_with_user(e) for e in self.emails]

        # Check that the user count increased for the email-based users
        self.assertEqual(User.objects.count(), 4)

        # Check that the users are in the query's shared_users
        self.assertEqual(query.shared_users.count(), 4)

    def test_duplicate_share(self):
        query = DataQuery(template=True, default=True)
        query.save()

        [query.share_with_user(e) for e in self.emails]

        share_count = query.shared_users.count()
        user_count = User.objects.count()

        # Make sure that requests to share with users that are already shared
        # with don't cause new user or shared_user entries.
        [query.share_with_user(e) for e in self.emails]

        self.assertEqual(share_count, query.shared_users.count())
        self.assertEqual(user_count, User.objects.count())

    def test_no_create_on_share(self):
        # Make sure we are starting with the anticipated number of users.
        self.assertEqual(User.objects.count(), 1)

        # Assign an email to the existing user
        User.objects.all().update(email=self.existing_email)

        query = DataQuery(template=True, default=True)
        query.save()

        self.assertEqual(query.shared_users.count(), 0)

        # Share with all the emails but, with create_user set to False, the
        # query should only be shared with the 1 existing user.
        [query.share_with_user(e, create_user=False) for e in self.emails]

        # Check that the user count increased for the email-based users
        self.assertEqual(User.objects.count(), 1)

        # Check that the users are in the query's shared_users
        self.assertEqual(query.shared_users.count(), 1)
