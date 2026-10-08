from django.contrib import admin

from .models import CourseYear, Expedient, Matricula, Student, Teacher


class ExpedientInline(admin.TabularInline):
    model = Expedient
    fields = ('number',)
    extra = 0


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_number', 'first_name', 'second_name', 'name', 'school_email')
    search_fields = ['first_name', 'second_name', 'name', 'id_number', 'school_email', 'expedients__number']
    inlines = [ExpedientInline]


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_number', 'first_name', 'second_name', 'name', 'school_email')
    search_fields = ['first_name', 'second_name', 'name', 'id_number', 'school_email']


@admin.register(Expedient)
class ExpedientAdmin(admin.ModelAdmin):
    list_display = ('id', 'number', 'student')
    search_fields = ['number', 'student__first_name', 'student__name', 'student__id_number']
    raw_id_fields = ('student',)


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('expedient', 'course_year', 'assignatura')
    list_filter = ('course_year',)
    search_fields = ['expedient__number']


@admin.register(CourseYear)
class CourseYearAdmin(admin.ModelAdmin):
    list_display = ('id', 'year')
