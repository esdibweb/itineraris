from crispy_forms.helper import FormHelper
from django import forms
from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(attrs={
            'placeholder': 'Usuari',
            'class': 'form-control',
        }),
    )
    password = forms.CharField(
        label='Contrasenya',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Contrasenya',
            'class': 'form-control',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
