from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from gcodex.models import CourseYear, Teacher
from gcodex.utils import get_students
from .models import (
    Activity, ActivityAward, ActivityExternal, ActivityInternalColaborate, ActivityInternalRepresent,
    Annotation, StudentHours,
)

DATE_WIDGET = forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')


class ActivityForm(forms.ModelForm):
    """Base form for every activity type, rendered with crispy-forms."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'


class ActivityInternalColaborateForm(ActivityForm):
    class Meta:
        model = ActivityInternalColaborate
        fields = ['title', 'date', 'description', 'teacher']
        labels = {
            'title': 'Títol',
            'date': 'Data',
            'description': 'Descripció',
            'teacher': 'Docent responsable',
        }
        widgets = {'date': DATE_WIDGET}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.render_hidden_fields = True

        # Only teachers of the latest imported school year can be selected
        latest_year = CourseYear.objects.order_by('-year').first()
        if latest_year:
            self.fields['teacher'].queryset = (
                Teacher.objects.filter(course_years=latest_year).order_by('complete_name')
            )
        else:
            self.fields['teacher'].queryset = Teacher.objects.none()


class ActivityAwardForm(ActivityForm):
    class Meta:
        model = ActivityAward
        fields = ['title', 'date', 'description', 'organitzation']
        labels = {
            'title': 'Títol',
            'date': 'Data',
            'description': 'Descripció',
            'organitzation': 'Entitat que atorga el premi',
        }
        widgets = {'date': DATE_WIDGET}


class ActivityInternalRepresentForm(ActivityForm):
    class Meta:
        model = ActivityInternalRepresent
        fields = ['date', 'type', 'title']
        labels = {
            'title': 'Títol',
            'date': 'Data',
            'type': 'Tipus',
        }
        widgets = {'date': DATE_WIDGET}


class ActivityExternalForm(ActivityForm):
    class Meta:
        model = ActivityExternal
        fields = ['title', 'date', 'description', 'organitzation']
        labels = {
            'title': 'Títol',
            'date': 'Data',
            'description': 'Descripció',
            'organitzation': "Entitat que certifica l'activitat",
        }
        widgets = {'date': DATE_WIDGET}


class StudentHoursForm(forms.ModelForm):
    notify = forms.BooleanField(required=False, label='Notificar')

    class Meta:
        model = StudentHours
        fields = ['student', 'hours']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = get_students()
        self.fields['student'].label = ''
        self.fields['hours'].label = ''
        self.fields['hours'].widget = forms.NumberInput(attrs={'style': 'max-width: 100px;'})


class StudentHoursInlineFormSet(BaseInlineFormSet):
    """Student rows of an activity; keeps each student's cached total of hours up to date."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Saved rows are shown read-only
        for form in self.forms:
            if form.instance.student_id and form.instance.hours:
                form.fields['student'].widget = forms.HiddenInput()
                form.fields['hours'].widget = forms.HiddenInput()

    def save(self, commit=True):
        instances = super().save(commit=False)

        if commit:
            for instance in instances:
                if instance.student_id:
                    instance.save()

        for obj in self.deleted_objects:
            obj.delete()

        if commit:
            # Include the previous student of any row whose student was changed
            student_ids = {instance.student_id for instance in instances if instance.student_id}
            student_ids |= {obj.student_id for obj in self.deleted_objects}
            for form in self.initial_forms:
                if 'student' in form.changed_data and form.initial.get('student'):
                    student_ids.add(form.initial['student'])

            for student_id in student_ids:
                Annotation.update_total_hours(student_id)

        return instances


StudentHoursFormSet = inlineformset_factory(
    Activity, StudentHours,
    formset=StudentHoursInlineFormSet,
    form=StudentHoursForm,
    fields=['student', 'hours'],
    extra=0,
    can_delete=True,
)


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = Annotation
        fields = ['date', 'observations']
        labels = {
            'date': 'Data pagament crèdits',
            'observations': 'Observacions',
        }
        widgets = {
            'observations': forms.Textarea(attrs={'cols': 80, 'rows': 5}),
            'date': DATE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Desar'))
