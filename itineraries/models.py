from django.db import models
from django.db.models import Sum
from tinymce.models import HTMLField

from gcodex.models import Student, Teacher


class Activity(models.Model):
    title = models.CharField(max_length=100)
    date = models.DateField()
    description = HTMLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-date', 'title']

    def __str__(self):
        return self.title

    def delete(self, *args, **kwargs):
        # Deleting the activity cascades to its hours, so refresh the affected students' totals
        student_ids = set(self.hours.values_list('student_id', flat=True))
        result = super().delete(*args, **kwargs)
        for student_id in student_ids:
            Annotation.update_total_hours(student_id)
        return result


class ActivityExternal(Activity):
    organitzation = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Activitat externa'
        verbose_name_plural = 'Activitats externes'
        permissions = (
            ('manage_act_external', 'Gestionar activitats externes'),
        )


class ActivityAward(Activity):
    organitzation = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Premi'
        verbose_name_plural = 'Premis'
        permissions = (
            ('manage_act_award', 'Gestionar premis alumnat'),
        )


class ActivityInternalRepresent(Activity):
    type = models.ForeignKey('ActivityInternalType', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = 'Activitat de representació'
        verbose_name_plural = 'Activitats de representació'
        permissions = (
            ('manage_act_int_repr', "Gestionar activitats de representació d'alumnat"),
        )


class ActivityInternalColaborate(Activity):
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, related_name='activities', null=True)

    class Meta:
        verbose_name = 'Activitat de col·laboració'
        verbose_name_plural = 'Activitats de col·laboració'
        permissions = (
            ('manage_act_int_colab', 'Gestionar hores de col·laboració internes'),
        )


class ActivityInternalType(models.Model):
    description = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Tipus d'activitat de representació"
        verbose_name_plural = "Tipus d'activitats de representació"
        permissions = (
            ('manage_act_types', 'Gestionar tipus activitats internes'),
        )

    def __str__(self):
        return self.description


class Annotation(models.Model):
    """Per-student record: credit payment, notes and the cached total of hours."""
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='annotation')
    date = models.DateField(
        verbose_name='Data pagament crèdits', null=True, blank=True,
        help_text='Data del pagament dels crèdits (pot ser nul·la)',
    )
    observations = models.TextField(verbose_name='Observacions', null=True, blank=True, help_text='Observacions')
    total_hours = models.IntegerField(verbose_name="Total d'hores", default=0)

    class Meta:
        verbose_name = 'Anotació'
        verbose_name_plural = 'Anotacions'
        ordering = ['-date']

    def __str__(self):
        return f'Anotació de {self.student} el {self.date}'

    @staticmethod
    def calculate_total_hours(student_id):
        return StudentHours.objects.filter(student_id=student_id).aggregate(total=Sum('hours'))['total'] or 0

    @classmethod
    def update_total_hours(cls, student_id):
        """Recompute and store the cached total of hours for a student."""
        cls.objects.update_or_create(
            student_id=student_id,
            defaults={'total_hours': cls.calculate_total_hours(student_id)},
        )


class StudentHours(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    hours = models.IntegerField()
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name='hours')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Activitat d'alumnat"
        verbose_name_plural = "Activitats d'alumnat"
        permissions = (
            ('manage_student_hours', "Consultar hores de l'alumnat"),
        )
        indexes = [
            models.Index(fields=['activity']),
        ]
