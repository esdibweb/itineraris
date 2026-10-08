from django.urls import path
from .views import CustomLoginView, CustomLogoutView, HomeView, AvatarView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('home/', HomeView.as_view(), name='home'),
    path('media/avatars/<str:username>/', AvatarView.as_view(), name='avatar_view'),
]
