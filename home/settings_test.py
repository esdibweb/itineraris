"""Settings for the test suite: python manage.py test --settings=home.settings_test"""
import os

# settings.py requires these at import time
os.environ.setdefault("SECRET_KEY", "test-only-not-secret")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver localhost")

from .settings import *  # noqa: E402,F401,F403

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Faster user creation in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
