from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from gcodex.models import Student
from itineraries.models import Annotation, StudentHours


class Command(BaseCommand):
    help = (
        "Compare each student's cached total of hours (Annotation.total_hours) with the sum of their "
        "StudentHours. Only reports by default; use --apply to save the corrected totals."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='save the corrected totals')

    def handle(self, *args, **options):
        actual = dict(
            StudentHours.objects.order_by().values('student')
            .annotate(total=Sum('hours')).values_list('student', 'total')
        )
        stored = dict(Annotation.objects.values_list('student', 'total_hours'))

        # A total is wrong if it differs from the sum, or if a student has hours but no annotation
        mismatches = []
        for student_id in actual.keys() | stored.keys():
            actual_total = actual.get(student_id) or 0
            stored_total = stored.get(student_id)
            if stored_total is None and actual_total == 0:
                continue
            if stored_total != actual_total:
                mismatches.append((student_id, stored_total, actual_total))

        if not mismatches:
            self.stdout.write(self.style.SUCCESS(f'All totals are correct ({len(stored)} annotations checked).'))
            return

        students = Student.objects.in_bulk([student_id for student_id, _, _ in mismatches])

        def sort_key(mismatch):
            student = students.get(mismatch[0])
            return (student.complete_name or '') if student else ''

        self.stdout.write(f'{len(mismatches)} students with a wrong total:')
        for student_id, stored_total, actual_total in sorted(mismatches, key=sort_key):
            student = students.get(student_id)
            name = student.complete_name if student else '?'
            stored_text = 'no annotation' if stored_total is None else stored_total
            self.stdout.write(f'  [{student_id}] {name}: stored {stored_text}, actual {actual_total}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Nothing was changed. Run with --apply to fix them.'))
            return

        with transaction.atomic():
            for student_id, _, _ in mismatches:
                Annotation.update_total_hours(student_id)
        self.stdout.write(self.style.SUCCESS(f'{len(mismatches)} totals fixed.'))
