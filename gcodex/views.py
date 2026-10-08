"""Import of students, enrolments and teachers from Codex CSV exports."""
import csv
from datetime import datetime
from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic.edit import FormView

from .forms import UploadCSVForm
from .models import CourseYear, Expedient, Matricula, Student, Teacher

REQUIRED_FIELDS_STUDENTS = [
    'Data', "Pla d'estudis", 'Curs escolar', 'Caràcter', 'Crèdits', 'Total crèdits', 'Estudis',
    'Especialitat', 'Curs', 'Període', 'Asignatura', 'Iteració', 'Reconeixements', 'Grup', 'Professors',
    'Dni profesores', 'Correo corporativo profesores', 'Expedient', 'Tiempo parcial', 'Estat matrícula',
    'Tipus de document', 'D.N.I/NIE/Passaport/Un altre', 'Primer cognom', 'Segon cognom', 'Nom',
    'Telèfon', 'Mòbil', 'Data de naixement', 'Email', 'Pàgina web/blog', 'Sexe', 'País de naixement',
    'Codi ISO de país', 'Ciutat de naixement', 'Codi INE', 'Província', 'Codi INE',
    'Comunitat Autònoma', 'Codi INE', 'Codi postal del lloc de naixement', 'Nacionalitat',
    'País de residència', 'Ciutat de residència', 'Codi INE', 'Província', 'Codi INE',
    'Comunitat Autònoma', 'Codi INE', 'Adreça', 'C.P.', 'Email corporativo', 'Nombre deseado',
    "Procés d'ingrès", "subprocés d'admissió", "Situacions de l'alumne",
]

REQUIRED_FIELDS_TEACHERS = [
    "Pla d'estudis", 'Curs escolar', 'Caràcter', 'Crèdits', 'Estudis', 'Especialitat', 'Curs', 'Període',
    'Asignatura', 'Grup', 'Tipus de document', 'D.N.I/NIE/Passaport/Un altre', 'Primer cognom',
    'Segon cognom', 'Nom', 'Telèfon', 'Mòbil', 'Data de naixement', 'Email', 'Pàgina web/blog', 'Sexe',
    'País de naixement', 'Codi ISO de país', 'Codi ISO de país', 'Codi ISO de país', 'Ciutat de naixement',
    'Codi INE', 'Província', 'Codi INE', 'Comunitat Autònoma', 'Codi INE',
    'Codi postal del lloc de naixement', 'Nacionalitat', 'Codi ISO de país', 'Codi ISO de país',
    'Codi ISO de país', 'País de residència', 'Codi ISO de país', 'Codi ISO de país', 'Codi ISO de país',
    'Ciutat de residència', 'Codi INE', 'Província', 'Codi INE', 'Comunitat Autònoma', 'Codi INE',
    'Adreça', 'C.P.', 'Email corporativo', 'Nombre deseado', 'Código de profesor',
]


BATCH_SIZE = 1000

# Student fields written by the import
STUDENT_FIELDS = [
    'id_number', 'type_id', 'name', 'first_name', 'second_name', 'phone', 'mobile', 'birthday', 'email',
    'country', 'city', 'province', 'region', 'postal_code', 'address', 'school_email', 'complete_name',
    'desired_name',
]


class ImportRowError(Exception):
    """A CSV row could not be imported; the whole import is rolled back."""

    def __init__(self, row_number, error):
        if isinstance(error, ValidationError):
            error = '; '.join(error.messages)
        super().__init__(f"Error a la línia {row_number}: {error}. No s'ha importat cap dada.")


def read_csv(csv_file):
    """Return a CSV reader for the upload (accepting Excel's BOM), or None if it is not UTF-8."""
    try:
        return csv.reader(csv_file.read().decode('utf-8-sig').splitlines())
    except UnicodeDecodeError:
        return None


def convert_date(date_string):
    """Parse 'DD/MM/YYYY' into a date, or None if invalid."""
    try:
        return datetime.strptime(date_string, '%d/%m/%Y').date()
    except ValueError:
        return None


def convert_datetime(datetime_string):
    """Parse 'DD/MM/YYYY HH:MM' into an aware datetime, or None if invalid."""
    try:
        return timezone.make_aware(datetime.strptime(datetime_string, '%d/%m/%Y %H:%M'))
    except ValueError:
        return None


def build_complete_name(first_name, second_name, name):
    if second_name:
        return f'{first_name} {second_name}, {name}'
    return f'{first_name}, {name}'


def person_fields(data):
    """Personal fields shared by students and teachers."""
    return {
        'type_id': data.get('Tipus de document'),
        'name': data.get('Nom'),
        'first_name': data.get('Primer cognom'),
        'second_name': data.get('Segon cognom'),
        'phone': data.get('Telèfon'),
        'mobile': data.get('Mòbil'),
        'birthday': convert_date(data.get('Data de naixement')),
        'email': data.get('Email'),
        'country': data.get('País de naixement'),
        'city': data.get('Ciutat de naixement'),
        'province': data.get('Província'),
        'region': data.get('Comunitat Autònoma'),
        'postal_code': data.get('Codi postal del lloc de naixement'),
        'address': data.get('Adreça'),
        'school_email': data.get('Email corporativo'),
        'complete_name': build_complete_name(data.get('Primer cognom'), data.get('Segon cognom'), data.get('Nom')),
    }


def model_values(model, values):
    """
    Convert values as Model.save() would and check text lengths, raising
    ValidationError so that a bad value can be reported with its CSV line.
    """
    cleaned = {}
    for name, value in values.items():
        field = model._meta.get_field(name)
        value = field.to_python(value)
        max_length = getattr(field, 'max_length', None)
        if isinstance(value, str) and max_length and len(value) > max_length:
            raise ValidationError(f"'{value}' supera els {max_length} caràcters")
        cleaned[name] = value
    return cleaned


def upsert_by_id_number(model, values_by_id_number):
    """Create or update people by id_number in bulk; return them keyed by id_number."""
    id_numbers = list(values_by_id_number)
    existing = model.objects.in_bulk(id_numbers, field_name='id_number')
    to_create, to_update = [], []
    for id_number, values in values_by_id_number.items():
        obj = existing.get(id_number)
        if obj is None:
            to_create.append(model(id_number=id_number, **values))
        elif apply_changes(obj, values):
            to_update.append(obj)

    model.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
    if to_update:
        fields = list(next(iter(values_by_id_number.values())))
        model.objects.bulk_update(to_update, fields, batch_size=BATCH_SIZE)
    return model.objects.in_bulk(id_numbers, field_name='id_number')


def apply_changes(obj, values):
    """Set values on obj; return whether anything changed. Foreign keys are compared by id to avoid queries."""
    changed = False
    for name, value in values.items():
        field = obj._meta.get_field(name)
        if field.is_relation:
            changed |= getattr(obj, field.attname) != (value.pk if value else None)
        else:
            changed |= getattr(obj, name) != value
        setattr(obj, name, value)
    return changed


def fit_row(row, column_count):
    """
    Return the row cut to column_count cells, or None if it does not match the header.
    Trailing empty cells beyond the header are allowed (exports often end lines with a comma).
    """
    if not row or len(row) < column_count or any(cell.strip() for cell in row[column_count:]):
        return None
    return row[:column_count]


def line_list(row_numbers, limit=20):
    """'3, 7, 9' or '3, 7, 9 i 12 més' for messages."""
    shown = ', '.join(str(number) for number in row_numbers[:limit])
    hidden = len(row_numbers) - limit
    return f'{shown} i {hidden} més' if hidden > 0 else shown


class BaseCSVImportView(PermissionRequiredMixin, FormView):
    """
    Validates the header and rows, then imports them inside a single transaction.

    Subclasses define `required_fields` and `import_rows()`, which receives
    (line number, {column: value}) pairs. Rows are written in bulk: a school
    year has thousands of enrolments, and saving them one by one exceeded the
    web server's request timeout.
    """
    form_class = UploadCSVForm
    permission_required = 'gcodex.import_codex_info'
    required_fields = []
    opt = None
    success_message = ''

    def form_valid(self, form):
        reader = read_csv(form.cleaned_data.get('csv_file'))
        if reader is None:
            messages.error(self.request, 'El fitxer CSV no està codificat en UTF-8.')
            return self.form_invalid(form)

        headers = next(reader, None)
        if headers is None:
            messages.error(self.request, 'El fitxer CSV està buit.')
            return self.form_invalid(form)
        # Codex exports may end the header line with a comma, i.e. an empty column name
        while headers and not headers[-1].strip():
            headers.pop()

        missing_fields = [field for field in self.required_fields if field not in headers]
        if missing_fields:
            messages.error(self.request, f'Falten les columnes següents: {", ".join(missing_fields)}')
            return self.form_invalid(form)

        header_indices = {header: index for index, header in enumerate(headers)}

        # The school year is taken from the first data row
        first_row = fit_row(next(reader, None), len(headers))
        if not first_row:
            messages.error(self.request, "No s'ha pogut detectar el curs escolar.")
            return self.form_invalid(form)
        course_year_name = first_row[header_indices['Curs escolar']]

        # Line 1 is the header, so data rows start at line 2
        rows, inconsistent = [], []
        for row_number, row in chain([(2, first_row)], enumerate(reader, start=3)):
            row = fit_row(row, len(headers))
            if row is None:
                inconsistent.append(row_number)
                continue
            rows.append((row_number, {field: row[header_indices[field]] for field in self.required_fields}))
        if inconsistent:
            messages.warning(self.request, f'Línies inconsistents, no importades: {line_list(inconsistent)}.')

        try:
            with transaction.atomic():
                self.import_rows(rows, course_year_name)
        except ImportRowError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except DatabaseError as e:
            messages.error(self.request, f"Error en desar les dades: {e}. No s'ha importat cap dada.")
            return self.form_invalid(form)

        messages.success(self.request, self.success_message.format(course_year=course_year_name))
        return super().form_valid(form)

    def import_rows(self, rows, course_year_name):
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['opt'] = self.opt
        return context


class UploadCSVStudentsView(BaseCSVImportView):
    """Imports students and replaces all enrolments of the school year."""
    template_name = 'gcodex/upload_alumnat.html'
    success_url = reverse_lazy('gcodex:alumnat')
    required_fields = REQUIRED_FIELDS_STUDENTS
    opt = 'alumnat'
    success_message = 'Dades del curs escolar {course_year} importades correctament'

    def import_rows(self, rows, course_year_name):
        # 1. Validate every row in memory, so errors point to a line and nothing is written yet
        students = {}         # id_number -> {'values', 'numbers' (files), 'line'}; the last row's data wins
        enrolments = []       # (expedient number, enrolment values); one row per subject
        expedient_lines = {}  # expedient number -> (id_number, line), to detect one file with two documents
        invalid_dates = []
        for row_number, data in rows:
            enrolment_date = convert_datetime(data['Data'])
            if enrolment_date is None or convert_date(data['Data de naixement']) is None:
                invalid_dates.append(row_number)
                continue
            id_number = data['D.N.I/NIE/Passaport/Un altre']
            try:
                expedient_number = int(data['Expedient'])
                other_id_number, other_line = expedient_lines.setdefault(expedient_number, (id_number, row_number))
                if other_id_number != id_number:
                    raise ValueError(
                        f"l'expedient {expedient_number} apareix amb un altre document a la línia {other_line}"
                    )
                student = students.setdefault(id_number, {'numbers': set()})
                student['values'] = model_values(
                    Student, {**person_fields(data), 'desired_name': data['Nombre deseado']},
                )
                student['numbers'].add(expedient_number)
                student['line'] = row_number
                enrolments.append((expedient_number, model_values(Matricula, {
                    'data': enrolment_date,
                    'pla_estudis': data["Pla d'estudis"],
                    'caracter': data['Caràcter'],
                    'credits': data['Crèdits'],
                    'total_credits': data['Total crèdits'],
                    'estudis': data['Estudis'],
                    'especialitat': data['Especialitat'],
                    'curs': data['Curs'],
                    'periode': data['Període'],
                    'assignatura': data['Asignatura'],
                    'iteracio': data['Iteració'],
                    'reconeixements': data['Reconeixements'],
                    'grup': data['Grup'],
                })))
            except (ValueError, ValidationError) as e:
                raise ImportRowError(row_number, e) from e

        if invalid_dates:
            messages.error(self.request, f'Línies amb una data incorrecta, no importades: {line_list(invalid_dates)}.')

        # 2. Replace the school year's enrolments with a few bulk queries
        course_year, _ = CourseYear.objects.get_or_create(year=course_year_name)
        Matricula.objects.filter(course_year=course_year).delete()

        numbers = {number for number, _ in enrolments}
        existing_numbers = Expedient.objects.in_bulk(list(numbers), field_name='number')
        Expedient.objects.bulk_create(
            [Expedient(number=number) for number in numbers if number not in existing_numbers],
            batch_size=BATCH_SIZE,
        )
        expedients = Expedient.objects.in_bulk(list(numbers), field_name='number')

        self.save_students(students, expedients)
        Matricula.objects.bulk_create(
            [
                Matricula(course_year=course_year, expedient=expedients[number], **values)
                for number, values in enrolments
            ],
            batch_size=BATCH_SIZE,
        )

    def save_students(self, students, expedients):
        """
        Create or update students and link them to their files.

        A student is matched by any of their files first, since a file number stays
        the same for their whole time at the school, and then by document number,
        which can change (e.g. a passport replaced by a NIE).
        """
        by_id_number = Student.objects.in_bulk(list(students), field_name='id_number')
        file_owners = Student.objects.in_bulk(
            [expedient.student_id for expedient in expedients.values() if expedient.student_id]
        )

        to_create, to_update, matched = [], [], {}
        for id_number, student_data in students.items():
            numbers, row_number = student_data['numbers'], student_data['line']
            candidates = {
                file_owners[expedients[number].student_id]
                for number in numbers if expedients[number].student_id
            }
            if id_number in by_id_number:
                candidates.add(by_id_number[id_number])
            if len(candidates) > 1:
                names = ' i '.join(sorted(candidate.complete_name or '?' for candidate in candidates))
                raise ImportRowError(
                    row_number, f'el document i els expedients corresponen a alumnes diferents: {names}',
                )

            values = {**student_data['values'], 'id_number': id_number}
            if not candidates:
                to_create.append(Student(**values))
                continue
            student = candidates.pop()
            if student.pk in matched:
                raise ImportRowError(
                    row_number, f'{student.complete_name} coincideix també amb la línia {matched[student.pk]}',
                )
            matched[student.pk] = row_number
            if apply_changes(student, values):
                to_update.append(student)

        Student.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
        Student.objects.bulk_update(to_update, STUDENT_FIELDS, batch_size=BATCH_SIZE)

        # Link every file in the CSV to its student; files from earlier years stay linked
        saved = Student.objects.in_bulk(list(students), field_name='id_number')
        relinked = []
        for id_number, student_data in students.items():
            for number in student_data['numbers']:
                expedient = expedients[number]
                if expedient.student_id != saved[id_number].pk:
                    expedient.student_id = saved[id_number].pk
                    relinked.append(expedient)
        Expedient.objects.bulk_update(relinked, ['student'], batch_size=BATCH_SIZE)


class UploadCSVTeachersView(BaseCSVImportView):
    """Imports teachers and replaces the teacher list of the school year."""
    template_name = 'gcodex/upload_docents.html'
    success_url = reverse_lazy('gcodex:docents')
    required_fields = REQUIRED_FIELDS_TEACHERS
    opt = 'docents'
    success_message = 'Dades de docents del curs escolar {course_year} importades correctament'

    def import_rows(self, rows, course_year_name):
        # One row per subject, so a teacher appears several times; the last row wins
        teachers = {}
        for row_number, data in rows:
            try:
                teachers[data['D.N.I/NIE/Passaport/Un altre']] = model_values(Teacher, person_fields(data))
            except ValidationError as e:
                raise ImportRowError(row_number, e) from e

        course_year, _ = CourseYear.objects.get_or_create(year=course_year_name)
        course_year.teacher_set.clear()
        saved = upsert_by_id_number(Teacher, teachers)

        # Each imported teacher is linked to this school year only
        through = Teacher.course_years.through
        teacher_ids = [teacher.id for teacher in saved.values()]
        through.objects.filter(teacher_id__in=teacher_ids).delete()
        through.objects.bulk_create(
            [through(teacher_id=teacher_id, courseyear_id=course_year.id) for teacher_id in teacher_ids],
            batch_size=BATCH_SIZE,
        )


class StudentListView(PermissionRequiredMixin, View):
    """JSON data for the students DataTable."""
    permission_required = 'gcodex.import_codex_info'

    def get(self, request, *args, **kwargs):
        data = [
            {
                'id_number': student.id_number,
                'complete_name': student.complete_name,
                'school_email': student.school_email,
            }
            for student in Student.objects.all()
        ]
        return JsonResponse({'data': data})
