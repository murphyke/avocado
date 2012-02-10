from django.test import TestCase
from django.db.models import Q
from django.core.cache import cache

from avocado.fields import logictree

class LogicTreeTestCase(TestCase):
    fixtures = ['test_data.yaml']

    def setUp(self):
        cache.clear()

    def test_single_field(self):
        raw_node = {
            'id': 1,
            'operator': 'iexact',
            'value': 'foobar'
        }

        q = logictree.transform(raw_node).condition
        self.assertEqual(str(q), str(Q(name__iexact=u'foobar')))

    def test_single_conditions(self):
        raw_node = {
            'type': 'and',
            'children': [{
                'id': 1,
                'operator': 'icontains',
                'value': 'test'
            }, {
                'id': 2,
                'operator': 'iexact',
                'value': 'test2'
            }]
        }

        q1 = logictree.transform(raw_node).condition
        q2 = Q(keywords__iexact=u'test2') & Q(name__icontains=u'test')
        self.assertEqual(str(q1), str(q2))

        raw_node['type'] = 'or'

        q3 = logictree.transform(raw_node).condition
        q4= Q(keywords__iexact=u'test2') | Q(name__icontains=u'test')
        self.assertEqual(str(q3), str(q4))

    def test_multi_level_condition(self):
        raw_node = {
            'type': 'and',
            'children': [{
                'id': 1,
                'operator': 'in',
                'value': ['one', 'two'],
            }, {
                'type': 'or',
                'children': [{
                    'id': 3,
                    'operator': 'iexact',
                    'value': 'foobar'
                }, {
                    'id': 3,
                    'operator': 'iexact',
                    'value': 'barbaz'
                }]
            }]
        }

        q1 = logictree.transform(raw_node).condition
        q2 = (Q(fields__name__iexact=u'barbaz') | Q(fields__name__iexact=u'foobar')) & Q(name__in=[u'one', u'two'])

        self.assertEqual(str(q1), str(q2))