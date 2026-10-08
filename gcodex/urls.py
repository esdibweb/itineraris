from django.urls import path

from . import views

app_name = 'gcodex'

urlpatterns = [
    path('', views.UploadCSVStudentsView.as_view(), name='alumnat'),
    path('docents', views.UploadCSVTeachersView.as_view(), name='docents'),

    # JSON data for DataTables
    path('students-data/', views.StudentListView.as_view(), name='students_data'),
]
