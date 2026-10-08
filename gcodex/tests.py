from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import CourseYear, Expedient, Matricula, Student, Teacher
from .views import REQUIRED_FIELDS_STUDENTS, REQUIRED_FIELDS_TEACHERS

YEAR = '2026-2027'


def csv_row(fields, **overrides):
    values = {
        'Data': '01/09/2026 10:00',
        'Curs escolar': YEAR,
        'Crèdits': '6',
        'Total crèdits': '60',
        'Expedient': '1001',
        'Tipus de document': 'DNI',
        'D.N.I/NIE/Passaport/Un altre': '11111111A',
        'Primer cognom': 'Cognom',
        'Segon cognom': 'Segon',
        'Nom': 'Nom',
        'Data de naixement': '01/01/2000',
        'Email': 'persona@example.com',
        'Email corporativo': 'persona@example.org',
        'Nombre deseado': 'Nom',
        **overrides,
    }
    return [values.get(field, '') for field in fields]


def student_row(expedient='1001', dni='11111111A', **overrides):
    overrides.update({'Expedient': expedient, 'D.N.I/NIE/Passaport/Un altre': dni})
    return csv_row(REQUIRED_FIELDS_STUDENTS, **overrides)


def csv_upload(rows, fields=REQUIRED_FIELDS_STUDENTS, bom=False):
    lines = [','.join(fields)] + [','.join(row) for row in rows]
    content = ('﻿' if bom else '') + '\n'.join(lines)
    return SimpleUploadedFile('codex.csv', content.encode('utf-8'), content_type='text/csv')


class ImportTestCase(TestCase):

    def setUp(self):
        user = get_user_model().objects.create_user('gestor', password='x')
        user.user_permissions.add(Permission.objects.get(codename='import_codex_info'))
        self.client.force_login(user)


class UploadStudentsTests(ImportTestCase):
    url = reverse('gcodex:alumnat')

    def upload(self, rows, **kwargs):
        return self.client.post(self.url, {'csv_file': csv_upload(rows, **kwargs)}, follow=True)

    def test_permission_from_gcodex_app_grants_access(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_csv_with_bom_is_imported(self):
        self.upload([student_row()], bom=True)
        self.assertTrue(Student.objects.filter(id_number='11111111A').exists())
        self.assertEqual(Matricula.objects.filter(course_year__year=YEAR).count(), 1)

    def test_failed_row_keeps_existing_enrolments(self):
        course_year = CourseYear.objects.create(year=YEAR)
        expedient = Expedient.objects.create(number=1)
        Matricula.objects.create(course_year=course_year, expedient=expedient)

        response = self.upload([student_row(), student_row(expedient='not-a-number', dni='22222222B')])

        self.assertContains(response, 'Error a la línia 3')
        self.assertEqual(list(Matricula.objects.values_list('expedient__number', flat=True)), [1])
        self.assertFalse(Student.objects.exists())

    def test_rows_with_invalid_dates_are_skipped(self):
        response = self.upload([student_row(), student_row(dni='22222222B', **{'Data de naixement': '2000-01-01'})])

        self.assertContains(response, 'Línies amb una data incorrecta, no importades: 3')
        self.assertEqual(list(Student.objects.values_list('id_number', flat=True)), ['11111111A'])

    def test_reimport_replaces_enrolments_and_updates_students(self):
        self.upload([student_row(), student_row()])
        self.upload([student_row(Nom='Nou'), student_row(Nom='Nou')])

        self.assertEqual(Matricula.objects.count(), 2)
        self.assertEqual(Student.objects.get().name, 'Nou')

    def make_student(self, id_number, *expedient_numbers, name='Nom'):
        student = Student.objects.create(
            type_id='DNI', id_number=id_number, name=name, first_name='Cognom', desired_name=name,
            complete_name=f'Cognom, {name}',
        )
        for number in expedient_numbers:
            Expedient.objects.create(number=number, student=student)
        return student

    def file_numbers(self, student):
        return sorted(student.expedients.values_list('number', flat=True))

    def test_changed_document_updates_the_student_with_that_expedient(self):
        student = self.make_student('PASSPORT1', 1762)

        self.upload([student_row(expedient='1762', dni='X1234567Z')])

        student.refresh_from_db()
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(student.id_number, 'X1234567Z')

    def test_student_with_two_expedients(self):
        self.upload([student_row(expedient='1'), student_row(expedient='2')])

        student = Student.objects.get()
        self.assertEqual(self.file_numbers(student), [1, 2])
        self.assertEqual(Matricula.objects.filter(expedient__student=student).count(), 2)

    def test_changed_document_is_matched_through_any_expedient(self):
        student = self.make_student('PASSPORT1', 1, 2)

        self.upload([student_row(expedient='2', dni='X1234567Z'), student_row(expedient='3', dni='X1234567Z')])

        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(self.file_numbers(student), [1, 2, 3])

    def test_document_and_expedient_of_different_students_is_an_error(self):
        self.make_student('11111111A', 1, name='Anna')
        self.make_student('22222222B', 2, name='Bernat')

        response = self.upload([student_row(expedient='2', dni='11111111A')])

        self.assertContains(response, 'Error a la línia 2: el document i els expedients corresponen a alumnes')
        self.assertEqual(self.file_numbers(Student.objects.get(name='Anna')), [1])

    def test_expedient_with_two_documents_in_the_file_is_an_error(self):
        response = self.upload([student_row(dni='11111111A'), student_row(dni='22222222B')])

        self.assertContains(response, 'Error a la línia 3')
        self.assertFalse(Student.objects.exists())

    def test_new_expedient_is_added_to_existing_student(self):
        student = self.make_student('11111111A', 1)

        self.upload([student_row(expedient='5', dni='11111111A')])

        self.assertEqual(self.file_numbers(student), [1, 5])

    def test_query_count_does_not_grow_with_rows(self):
        # One query per row made imports of a whole school year exceed the request timeout
        rows = [student_row(expedient=str(1000 + i), dni=f'{i:08d}X') for i in range(300)]
        with CaptureQueriesContext(connection) as queries:
            self.upload(rows)
        self.assertEqual(Matricula.objects.count(), 300)
        self.assertLess(len(queries), 50)


class UploadTeachersTests(ImportTestCase):
    url = reverse('gcodex:docents')

    def test_teacher_is_linked_only_to_the_imported_year(self):
        teacher = Teacher.objects.create(type_id='DNI', id_number='33333333C', name='Old', first_name='Cognom')
        teacher.course_years.add(CourseYear.objects.create(year='2025-2026'))

        # A teacher has one row per subject
        rows = [csv_row(REQUIRED_FIELDS_TEACHERS, **{'D.N.I/NIE/Passaport/Un altre': '33333333C'})] * 2
        self.client.post(self.url, {'csv_file': csv_upload(rows, fields=REQUIRED_FIELDS_TEACHERS)})

        teacher.refresh_from_db()
        self.assertEqual(teacher.name, 'Nom')
        self.assertEqual(list(teacher.course_years.values_list('year', flat=True)), [YEAR])
