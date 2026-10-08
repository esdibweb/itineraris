from django.contrib import admin

from .models import (
    ActivityAward, ActivityExternal, ActivityInternalColaborate, ActivityInternalRepresent, ActivityInternalType,
    Annotation, StudentHours,
)


@admin.register(ActivityExternal, ActivityInternalRepresent, ActivityAward, ActivityInternalColaborate)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'date')


@admin.register(StudentHours)
class StudentHoursAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'activity', 'hours')
    search_fields = [
        'student__first_name', 'student__second_name', 'student__name', 'student__id_number',
        'student__school_email', 'activity__title',
    ]


@admin.register(ActivityInternalType)
class ActivityInternalTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'description')


@admin.register(Annotation)
class AnnotationAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'date', 'observations', 'total_hours')
