import os

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from .forms import LoginForm

User = get_user_model()


class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('home')


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('login')


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'users/home.html'


class AvatarView(LoginRequiredMixin, View):
    """Serves a user's avatar from the media folder, to logged-in users only."""

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        if not user.avatar or not os.path.exists(user.avatar.path):
            raise Http404('Avatar not found.')
        return FileResponse(open(user.avatar.path, 'rb'), content_type='image/jpeg')
