try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
from django.test import TestCase
from django.core import management
from avocado.models import DataField, DataConcept, DataConceptField
from avocado.formatters import Formatter


__all__ = ['FormatterTestCase']


class FormatterTestCase(TestCase):
    fixtures = ['formatters.json']

    def setUp(self):
        management.call_command('avocado', 'sync', 'formatters', quiet=True)
        name_field = DataField.objects.get_by_natural_key('formatters', 'title', 'name')
        salary_field = DataField.objects.get_by_natural_key('formatters', 'title', 'salary')
        boss_field = DataField.objects.get_by_natural_key('formatters', 'title', 'boss')

        self.concept = concept = DataConcept(name='Title')
        concept.save()

        DataConceptField(concept=concept, field=name_field, order=1).save()
        DataConceptField(concept=concept, field=salary_field, order=2).save()
        DataConceptField(concept=concept, field=boss_field, order=3).save()

        self.values = ['CEO', 100000, True]
        self.f = Formatter(concept)

    def test_to_string(self):
        fvalues = self.f(self.values, preferred_formats=['string'])
        self.assertEqual(OrderedDict([
            ('name', 'CEO'),
            ('salary', '100000'),
            ('boss', 'True'),
        ]), fvalues)

    def test_to_number(self):
        fvalues = self.f(self.values, preferred_formats=['number'])
        self.assertEqual(OrderedDict([
            ('name', 'CEO'),
            ('salary', 100000),
            ('boss', 1),
        ]), fvalues)

    def test_to_boolean(self):
        fvalues = self.f(self.values, preferred_formats=['boolean'])
        self.assertEqual(OrderedDict([
            ('name', 'CEO'),
            ('salary', 100000),
            ('boss', True),
        ]), fvalues)

    def test_to_coded(self):
        fvalues = self.f(self.values, preferred_formats=['coded'])
        self.assertEqual(OrderedDict([
            ('name', 'CEO'),
            ('salary', 100000),
            ('boss', 1),
        ]), fvalues)

    def test_to_html(self):
        class HtmlFormatter(Formatter):
            def to_html(self, values, **context):
                fvalues = self(values, preferred_formats=['string'])
                return OrderedDict({
                    'profile': '<span>' + '</span><span>'.join(fvalues.values()) + '</span>'
                })
            to_html.process_multiple = True

        f = HtmlFormatter(self.concept)
        fvalues = f(self.values, preferred_formats=['html'])
        self.assertEqual(OrderedDict({
            'profile': u'<span>CEO</span><span>100000</span><span>True</span>'
        }), fvalues)
