import logging
from io import BytesIO
from urllib.parse import urlparse

import requests
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image

User = get_user_model()
logger = logging.getLogger(__name__)

# Avatars only come from Google's image hosts, over HTTPS, with bounded time and size
AVATAR_HOST_SUFFIX = '.googleusercontent.com'
AVATAR_TIMEOUT = 5
AVATAR_MAX_BYTES = 2 * 1024 * 1024


def get_verified_email(sociallogin):
    """Return the email address verified by the provider, or None."""
    for address in sociallogin.email_addresses:
        if address.verified and address.email:
            return address.email
    return None


def fetch_avatar(url):
    """Download the avatar and return its bytes if it is a valid image, otherwise None."""
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not (parsed.hostname or '').endswith(AVATAR_HOST_SUFFIX):
        return None
    try:
        with requests.get(url, timeout=AVATAR_TIMEOUT, stream=True, allow_redirects=False) as response:
            response.raise_for_status()
            data = b''
            for chunk in response.iter_content(64 * 1024):
                data += chunk
                if len(data) > AVATAR_MAX_BYTES:
                    return None
        Image.open(BytesIO(data)).verify()
        return data
    except Exception as e:
        logger.warning('Could not download avatar: %s', e)
        return None


class AccountAdapter(DefaultAccountAdapter):

    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user

        # Link to an existing user only when the provider has verified the email
        if not user.id:
            email = get_verified_email(sociallogin)
            if email:
                matches = list(User.objects.filter(email__iexact=email)[:2])
                if len(matches) == 1:
                    sociallogin.connect(request, matches[0])
                    user = matches[0]

        avatar_url = sociallogin.account.extra_data.get('picture')
        if avatar_url:
            self.save_avatar(user, avatar_url)

    def save_avatar(self, user, avatar_url):
        image_data = fetch_avatar(avatar_url)
        if not image_data:
            return
        if user.avatar:
            user.avatar.delete(save=False)
        # A new user is saved later, when the signup completes
        user.avatar.save(f'{user.username}_avatar.jpg', ContentFile(image_data), save=bool(user.id))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        email = data.get('email')
        if email:
            user.email = email
            user.username = email.split('@')[0]
        return user

    def is_open_for_signup(self, request, sociallogin):
        # Only verified addresses from the school's Google domains can create an account
        email = get_verified_email(sociallogin)
        if not email:
            return False
        return email.rsplit('@', 1)[-1].lower() in settings.ALLOWED_SIGNUP_DOMAINS
