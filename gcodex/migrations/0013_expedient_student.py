"""
A student can have several files (one per programme): move the link from
Student.expedient (one-to-one) to Expedient.student (many files per student).
"""
import django.db.models.deletion
from django.db import migrations, models


def copy_links_to_expedients(apps, schema_editor):
    Expedient = apps.get_model('gcodex', 'Expedient')
    Student = apps.get_model('gcodex', 'Student')
    expedients = []
    for student_id, expedient_id in Student.objects.filter(expedient__isnull=False).values_list('id', 'expedient_id'):
        expedients.append(Expedient(id=expedient_id, student_id=student_id))
    Expedient.objects.bulk_update(expedients, ['student'], batch_size=1000)


def copy_links_to_students(apps, schema_editor):
    """Reverse: keep each student's most recent file (highest number)."""
    Expedient = apps.get_model('gcodex', 'Expedient')
    Student = apps.get_model('gcodex', 'Student')
    latest = {}
    for expedient_id, student_id in (
        Expedient.objects.filter(student__isnull=False).order_by('number').values_list('id', 'student_id')
    ):
        latest[student_id] = expedient_id
    students = [Student(id=student_id, expedient_id=expedient_id) for student_id, expedient_id in latest.items()]
    Student.objects.bulk_update(students, ['expedient'], batch_size=1000)


class Migration(migrations.Migration):

    dependencies = [
        ('gcodex', '0012_alter_student_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='expedient',
            name='student',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='expedients', to='gcodex.student',
            ),
        ),
        migrations.RunPython(copy_links_to_expedients, copy_links_to_students),
        migrations.RemoveField(
            model_name='student',
            name='expedient',
        ),
    ]
