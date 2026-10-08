from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from mailer import send_mail

from gcodex.models import Student
from .forms import (
    ActivityAwardForm, ActivityExternalForm, ActivityInternalColaborateForm, ActivityInternalRepresentForm,
    AnnotationForm, StudentHoursFormSet,
)
from .models import (
    ActivityAward, ActivityExternal, ActivityInternalColaborate, ActivityInternalRepresent, Annotation,
    StudentHours,
)


def student_hours_context(student):
    student_hours = StudentHours.objects.filter(student=student).order_by('activity__date')
    return {
        'student': student,
        'student_hours': student_hours,
        'total_hours': student_hours.aggregate(total=Sum('hours'))['total'] or 0,
    }


# Index pages

class IndexView(PermissionRequiredMixin, View):
    template_name = 'itineraries/index.html'
    permission_required = (
        'itineraries.manage_student_hours',
        'itineraries.manage_act_int_colab',
        'itineraries.manage_act_external',
        'itineraries.manage_act_int_repr',
        'itineraries.manage_act_award',
    )

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)


class BaseIndexView(View):
    template_name = None
    opt = None

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'opt': self.opt})


class IndexAlumnat(PermissionRequiredMixin, BaseIndexView):
    template_name = 'itineraries/llistats/llistat_alumnat.html'
    opt = 'alumnat'
    permission_required = 'itineraries.manage_student_hours'


class IndexActivityInternalColaborate(PermissionRequiredMixin, BaseIndexView):
    template_name = 'itineraries/llistats/llistat_internes.html'
    opt = 'internes'
    permission_required = 'itineraries.manage_act_int_colab'


class IndexActivityAward(PermissionRequiredMixin, BaseIndexView):
    template_name = 'itineraries/llistats/llistat_premis.html'
    opt = 'premis'
    permission_required = 'itineraries.manage_act_award'


class IndexActivityInternalRepresent(PermissionRequiredMixin, BaseIndexView):
    template_name = 'itineraries/llistats/llistat_representacio.html'
    opt = 'representacio'
    permission_required = 'itineraries.manage_act_int_repr'


class IndexActivityExternal(PermissionRequiredMixin, BaseIndexView):
    template_name = 'itineraries/llistats/llistat_externes.html'
    opt = 'externes'
    permission_required = 'itineraries.manage_act_external'


# Student hours

class AlumnatHoresPublicView(LoginRequiredMixin, View):
    """A student's own hours, matched by the school email of the logged-in user."""
    template_name = 'itineraries/public/hores_alumnat.html'

    def get(self, request, *args, **kwargs):
        # Discard pending messages: they belong to the staff pages
        list(messages.get_messages(request))

        student = Student.objects.filter(school_email=request.user.email).first()
        if student:
            context = student_hours_context(student)
        else:
            context = {
                'error_message': "No s'ha trobat cap alumne amb aquest correu electrònic. "
                                 "Contacti amb administració.",
            }
        context['show_messages'] = False
        return render(request, self.template_name, context)


class AlumnatHoresView(PermissionRequiredMixin, View):
    """Staff view of a student's hours, with the credit payment annotation."""
    template_name = 'itineraries/hores_fetes.html'
    permission_required = 'itineraries.manage_student_hours'
    success_url = reverse_lazy('itineraries:alumnat')

    def get_context(self, pk, form=None):
        student = get_object_or_404(Student, id=pk)
        annotation, _ = Annotation.objects.get_or_create(student=student)
        context = student_hours_context(student)
        context['form'] = form or AnnotationForm(instance=annotation)
        context['opt'] = 'alumnat'
        return context

    def get(self, request, pk, *args, **kwargs):
        return render(request, self.template_name, self.get_context(pk))

    def post(self, request, pk, *args, **kwargs):
        student = get_object_or_404(Student, id=pk)
        annotation, _ = Annotation.objects.get_or_create(student=student)
        form = AnnotationForm(request.POST, instance=annotation)
        if form.is_valid():
            form.save()
            return redirect(self.success_url)
        return render(request, self.template_name, self.get_context(pk, form))


# Create and update

class BaseActivityFormView:
    """
    Activity form plus the formset of student hours.

    Subclasses set `extra_rows`, the number of empty student rows shown.
    """
    extra_rows = 1
    is_edit = False
    opt = None

    def get_extra_rows(self):
        return self.extra_rows

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formset_class = type('StudentHoursFormSet', (StudentHoursFormSet,), {'extra': self.get_extra_rows()})
        if self.request.POST:
            context['student_hours_formset'] = formset_class(self.request.POST, instance=self.object)
        else:
            context['student_hours_formset'] = formset_class(instance=self.object)
        context['opt'] = self.opt
        context['is_edit'] = self.is_edit
        return context

    def form_valid(self, form):
        form.instance.author = self.request.user
        student_hours_formset = self.get_context_data()['student_hours_formset']
        if not student_hours_formset.is_valid():
            return self.form_invalid(form)

        self.object = form.save()
        student_hours_formset.instance = self.object

        for student_hours_form in student_hours_formset:
            instance = student_hours_form.instance
            if not instance.author or {'hours', 'student'} & set(student_hours_form.changed_data):
                instance.author = self.request.user

            if (student_hours_form.cleaned_data.get('notify')
                    and student_hours_form not in student_hours_formset.deleted_forms
                    and instance.student.school_email):
                send_mail(
                    "Actualització d'hores d'itinerari extracurricular",
                    f'S\'han actualizat per a l\'activitat "{instance.activity}" un total de '
                    f'{instance.hours} hores al vostre expedient.',
                    None,  # DEFAULT_FROM_EMAIL
                    [instance.student.school_email],
                    fail_silently=False,
                )

        student_hours_formset.save()
        return super().form_valid(form)


class ActivityInternalColaborateCreateView(PermissionRequiredMixin, BaseActivityFormView, CreateView):
    model = ActivityInternalColaborate
    form_class = ActivityInternalColaborateForm
    template_name = 'itineraries/forms/form_internes.html'
    success_url = reverse_lazy('itineraries:internes')
    opt = 'internes'
    permission_required = 'itineraries.manage_act_int_colab'
    extra_rows = 12


class ActivityAwardCreateView(PermissionRequiredMixin, BaseActivityFormView, CreateView):
    model = ActivityAward
    form_class = ActivityAwardForm
    template_name = 'itineraries/forms/form_premis.html'
    success_url = reverse_lazy('itineraries:premis')
    opt = 'premis'
    permission_required = 'itineraries.manage_act_award'
    extra_rows = 1


class ActivityInternalRepresentCreateView(PermissionRequiredMixin, BaseActivityFormView, CreateView):
    model = ActivityInternalRepresent
    form_class = ActivityInternalRepresentForm
    template_name = 'itineraries/forms/form_representacio.html'
    success_url = reverse_lazy('itineraries:representacio')
    opt = 'representacio'
    permission_required = 'itineraries.manage_act_int_repr'
    extra_rows = 10


class ActivityExternalCreateView(PermissionRequiredMixin, BaseActivityFormView, CreateView):
    model = ActivityExternal
    form_class = ActivityExternalForm
    template_name = 'itineraries/forms/form_externes.html'
    success_url = reverse_lazy('itineraries:externes')
    opt = 'externes'
    permission_required = 'itineraries.manage_act_external'
    extra_rows = 12


class ActivityInternalColaborateUpdateView(PermissionRequiredMixin, BaseActivityFormView, UpdateView):
    model = ActivityInternalColaborate
    form_class = ActivityInternalColaborateForm
    template_name = 'itineraries/forms/form_internes.html'
    success_url = reverse_lazy('itineraries:internes')
    opt = 'internes'
    permission_required = 'itineraries.manage_act_int_colab'
    extra_rows = 12
    is_edit = True


class ActivityAwardUpdateView(PermissionRequiredMixin, BaseActivityFormView, UpdateView):
    model = ActivityAward
    form_class = ActivityAwardForm
    template_name = 'itineraries/forms/form_premis.html'
    success_url = reverse_lazy('itineraries:premis')
    opt = 'premis'
    permission_required = 'itineraries.manage_act_award'
    is_edit = True

    def get_extra_rows(self):
        # An award belongs to a single student: only offer a row while there is none
        return 0 if self.object.hours.exists() else 1


class ActivityInternalRepresentUpdateView(PermissionRequiredMixin, BaseActivityFormView, UpdateView):
    model = ActivityInternalRepresent
    form_class = ActivityInternalRepresentForm
    template_name = 'itineraries/forms/form_representacio.html'
    success_url = reverse_lazy('itineraries:representacio')
    opt = 'representacio'
    permission_required = 'itineraries.manage_act_int_repr'
    extra_rows = 10
    is_edit = True


class ActivityExternalUpdateView(PermissionRequiredMixin, BaseActivityFormView, UpdateView):
    model = ActivityExternal
    form_class = ActivityExternalForm
    template_name = 'itineraries/forms/form_externes.html'
    success_url = reverse_lazy('itineraries:externes')
    opt = 'externes'
    permission_required = 'itineraries.manage_act_external'
    extra_rows = 12
    is_edit = True


# Delete

class BaseActivityDeleteView(DeleteView):
    success_message = "L'activitat ha estat eliminada correctament."

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class ActivityInternalColaborateDeleteView(PermissionRequiredMixin, BaseActivityDeleteView):
    model = ActivityInternalColaborate
    success_url = reverse_lazy('itineraries:internes')
    permission_required = 'itineraries.manage_act_int_colab'


class ActivityAwardDeleteView(PermissionRequiredMixin, BaseActivityDeleteView):
    model = ActivityAward
    success_url = reverse_lazy('itineraries:premis')
    permission_required = 'itineraries.manage_act_award'


class ActivityInternalRepresentDeleteView(PermissionRequiredMixin, BaseActivityDeleteView):
    model = ActivityInternalRepresent
    success_url = reverse_lazy('itineraries:representacio')
    permission_required = 'itineraries.manage_act_int_repr'


class ActivityExternalDeleteView(PermissionRequiredMixin, BaseActivityDeleteView):
    model = ActivityExternal
    success_url = reverse_lazy('itineraries:externes')
    permission_required = 'itineraries.manage_act_external'


# JSON data for DataTables

class BaseActivityListView(View):
    model = None

    def serialize(self, activity):
        return {
            'id': activity.id,
            'title': activity.title,
            'date': activity.date.strftime('%d-%m-%Y'),
        }

    def get(self, request, *args, **kwargs):
        return JsonResponse({'data': [self.serialize(activity) for activity in self.model.objects.all()]})


class ActivityInternalColaborateListView(PermissionRequiredMixin, BaseActivityListView):
    model = ActivityInternalColaborate
    permission_required = 'itineraries.manage_act_int_colab'


class ActivityInternalRepresentListView(PermissionRequiredMixin, BaseActivityListView):
    model = ActivityInternalRepresent
    permission_required = 'itineraries.manage_act_int_repr'


class ActivityExternalListView(PermissionRequiredMixin, BaseActivityListView):
    model = ActivityExternal
    permission_required = 'itineraries.manage_act_external'

    def serialize(self, activity):
        return {**super().serialize(activity), 'organitzation': activity.organitzation}


class ActivityAwardListView(PermissionRequiredMixin, BaseActivityListView):
    model = ActivityAward
    permission_required = 'itineraries.manage_act_award'

    def serialize(self, activity):
        student_hours = StudentHours.objects.filter(activity=activity).select_related('student').first()
        return {
            **super().serialize(activity),
            'organitzation': activity.organitzation,
            'student': student_hours.student.complete_name if student_hours else None,
        }


class StudentHoursListView(PermissionRequiredMixin, View):
    """Students with at least one hour, using the cached total."""
    permission_required = 'itineraries.manage_student_hours'

    def get(self, request, *args, **kwargs):
        students = Student.objects.select_related('annotation').filter(annotation__total_hours__gt=0)
        data = [
            {
                'id': student.id,
                'id_number': student.id_number,
                'complete_name': student.complete_name,
                'school_email': student.school_email,
                'total_hours': student.annotation.total_hours,
            }
            for student in students
        ]
        return JsonResponse({'data': data})
