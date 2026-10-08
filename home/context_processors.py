from django.conf import settings


def app_version(request):
    """Version of the running build, shown in the page header and footer."""
    return {'app_version': settings.APP_VERSION}
