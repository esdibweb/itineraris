from .models import Student


def get_students():
    return Student.objects.all().order_by('complete_name')
