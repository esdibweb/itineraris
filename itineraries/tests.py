import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from gcodex.models import Student
from .forms import StudentHoursFormSet
from .models import (
    Activity, ActivityAward, ActivityExternal, ActivityInternalColaborate, ActivityInternalRepresent, Annotation,
    StudentHours,
)


def make_student(id_number):
    return Student.objects.create(type_id='DNI', id_number=id_number, name='Nom',
                                  first_name='Cognom', second_name='', desired_name='Nom')


class StudentHoursFormSetTests(TestCase):

    def test_changing_student_recalculates_previous_student_total(self):
        old, new = make_student('A'), make_student('B')
        activity = Activity.objects.create(title='Activitat', date=datetime.date(2026, 10, 1))
        hours = StudentHours.objects.create(student=old, activity=activity, hours=5)
        Annotation.objects.create(student=old, total_hours=5)

        prefix = StudentHoursFormSet.get_default_prefix()
        formset = StudentHoursFormSet({
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '1',
            f'{prefix}-0-id': str(hours.id),
            f'{prefix}-0-student': str(new.id),
            f'{prefix}-0-hours': '5',
        }, instance=activity)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()

        self.assertEqual(Annotation.objects.get(student=old).total_hours, 0)
        self.assertEqual(Annotation.objects.get(student=new).total_hours, 5)


class RecalculateHoursCommandTests(TestCase):

    def setUp(self):
        self.stale, self.missing = make_student('A'), make_student('B')
        activity = Activity.objects.create(title='Activitat', date=datetime.date(2026, 10, 1))
        StudentHours.objects.create(student=self.missing, activity=activity, hours=3)
        Annotation.objects.create(student=self.stale, total_hours=5)

    def test_report_only_does_not_modify(self):
        out = StringIO()
        call_command('recalculate_hours', stdout=out)
        self.assertIn('2 students', out.getvalue())
        self.assertEqual(Annotation.objects.get(student=self.stale).total_hours, 5)
        self.assertFalse(Annotation.objects.filter(student=self.missing).exists())

    def test_apply_fixes_totals(self):
        call_command('recalculate_hours', '--apply', stdout=StringIO())
        self.assertEqual(Annotation.objects.get(student=self.stale).total_hours, 0)
        self.assertEqual(Annotation.objects.get(student=self.missing).total_hours, 3)


class PageSmokeTests(TestCase):
    """Every page renders for an administrator."""

    def setUp(self):
        user =get_user_model().objects.create_superuser('admin', email='admin@example.org', password='x')
        self.client.force_login(user)
        self.student = make_student('A')
        self.student.school_email = 'admin@example.org'
        self.student.save()

        date = datetime.date(2026, 10, 1)
        self.activities = {
            'internes': ActivityInternalColaborate.objects.create(title='<b>Interna</b>', date=date),
            'premis': ActivityAward.objects.create(title='Premi', date=date, organitzation='Org'),
            'representacio': ActivityInternalRepresent.objects.create(title='Repr', date=date),
            'externes': ActivityExternal.objects.create(title='Externa', date=date, organitzation='Org'),
        }
        for activity in self.activities.values():
            StudentHours.objects.create(student=self.student, activity=activity, hours=2)
        Annotation.update_total_hours(self.student.id)

    def assert_ok(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return response

    def test_pages_render(self):
        for name in ['home', 'itineraries:index', 'itineraries:public', 'itineraries:alumnat',
                     'itineraries:students_hours_data', 'gcodex:alumnat', 'gcodex:docents', 'gcodex:students_data']:
            self.assert_ok(reverse(name))
        self.assert_ok(reverse('itineraries:alumnat_hores', args=[self.student.id]))

        for opt, activity in self.activities.items():
            self.assert_ok(reverse(f'itineraries:{opt}'))
            self.assert_ok(reverse(f'itineraries:nova_{opt}'))
            self.assert_ok(reverse(f'itineraries:edit_{opt}', args=[activity.id]))
            data = self.assert_ok(reverse(f'itineraries:{opt}_data')).json()['data']
            self.assertEqual(len(data), 1)

    def test_deleting_activity_updates_student_total(self):
        response = self.client.post(reverse('itineraries:delete_premis', args=[self.activities['premis'].id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Annotation.objects.get(student=self.student).total_hours, 6)

    @override_settings(APP_VERSION='2026.10.08-abc1234')
    def test_version_is_shown(self):
        self.assertContains(self.client.get(reverse('home')), 'v2026.10.08-abc1234')
        self.client.logout()
        self.assertContains(self.client.get(reverse('login')), 'Versió 2026.10.08-abc1234')
