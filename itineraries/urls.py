from django.urls import path

from . import views

app_name = 'itineraries'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('public', views.AlumnatHoresPublicView.as_view(), name='public'),

    path('alumnat', views.IndexAlumnat.as_view(), name='alumnat'),
    path('alumnat/<int:pk>/hores/', views.AlumnatHoresView.as_view(), name='alumnat_hores'),

    path('internes', views.IndexActivityInternalColaborate.as_view(), name='internes'),
    path('internes/nova', views.ActivityInternalColaborateCreateView.as_view(), name='nova_internes'),
    path('internes/<int:pk>/edit/', views.ActivityInternalColaborateUpdateView.as_view(), name='edit_internes'),
    path('internes/<int:pk>/delete/', views.ActivityInternalColaborateDeleteView.as_view(), name='delete_internes'),

    path('premis', views.IndexActivityAward.as_view(), name='premis'),
    path('premis/nova', views.ActivityAwardCreateView.as_view(), name='nova_premis'),
    path('premis/<int:pk>/edit/', views.ActivityAwardUpdateView.as_view(), name='edit_premis'),
    path('premis/<int:pk>/delete/', views.ActivityAwardDeleteView.as_view(), name='delete_premis'),

    path('representacio', views.IndexActivityInternalRepresent.as_view(), name='representacio'),
    path('representacio/nova', views.ActivityInternalRepresentCreateView.as_view(),
         name='nova_representacio'),
    path('representacio/<int:pk>/edit/', views.ActivityInternalRepresentUpdateView.as_view(),
         name='edit_representacio'),
    path('representacio/<int:pk>/delete/', views.ActivityInternalRepresentDeleteView.as_view(),
         name='delete_representacio'),

    path('externes', views.IndexActivityExternal.as_view(), name='externes'),
    path('externes/nova', views.ActivityExternalCreateView.as_view(), name='nova_externes'),
    path('externes/<int:pk>/edit/', views.ActivityExternalUpdateView.as_view(), name='edit_externes'),
    path('externes/<int:pk>/delete/', views.ActivityExternalDeleteView.as_view(), name='delete_externes'),

    # JSON data for DataTables
    path('internes-data', views.ActivityInternalColaborateListView.as_view(), name='internes_data'),
    path('premis-data', views.ActivityAwardListView.as_view(), name='premis_data'),
    path('representacio-data', views.ActivityInternalRepresentListView.as_view(), name='representacio_data'),
    path('externes-data', views.ActivityExternalListView.as_view(), name='externes_data'),
    path('students-hours', views.StudentHoursListView.as_view(), name='students_hours_data'),
]
