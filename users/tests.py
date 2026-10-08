from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from home.security import client_ip
from .adapters import SocialAccountAdapter, fetch_avatar

User = get_user_model()


def google_login(email, verified):
    account = SocialAccount(provider='google', uid='123', extra_data={'email': email})
    return SocialLogin(user=User(email=email), account=account,
                       email_addresses=[EmailAddress(email=email, verified=verified, primary=True)])


class SocialAccountAdapterTests(TestCase):

    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get('/')
        self.existing = User.objects.create_user('docent', email='docent@example.org')

    def test_unverified_email_does_not_link_existing_user(self):
        sociallogin = google_login('docent@example.org', verified=False)
        with mock.patch.object(SocialLogin, 'connect') as connect:
            self.adapter.pre_social_login(self.request, sociallogin)
        connect.assert_not_called()
        self.assertFalse(self.adapter.is_open_for_signup(self.request, sociallogin))

    def test_verified_email_links_existing_user(self):
        sociallogin = google_login('Docent@example.org', verified=True)
        with mock.patch.object(SocialLogin, 'connect') as connect:
            self.adapter.pre_social_login(self.request, sociallogin)
        connect.assert_called_once_with(self.request, self.existing)

    def test_populate_user_without_email_does_not_crash(self):
        sociallogin = google_login('', verified=False)
        user = self.adapter.populate_user(self.request, sociallogin, {})
        self.assertIsNotNone(user)


class FetchAvatarTests(TestCase):

    def test_rejects_urls_outside_google(self):
        with mock.patch('users.adapters.requests.get') as get:
            self.assertIsNone(fetch_avatar('https://attacker.example.com/a.jpg'))
            self.assertIsNone(fetch_avatar('http://lh3.googleusercontent.com/a.jpg'))
        get.assert_not_called()


class SignupDomainTests(TestCase):

    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get('/')

    def test_school_domains_can_sign_up(self):
        for email in ['docent@escoladisseny.com', 'Alumne@ALUM.escoladisseny.com']:
            self.assertTrue(self.adapter.is_open_for_signup(self.request, google_login(email, verified=True)), email)

    def test_other_domains_cannot_sign_up(self):
        for email in ['someone@gmail.com', 'x@escoladisseny.com.attacker.example', 'x@fakeescoladisseny.com']:
            self.assertFalse(self.adapter.is_open_for_signup(self.request, google_login(email, verified=True)), email)


class AccessTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('docent', password='correct-password')

    def test_avatar_requires_login(self):
        response = self.client.get(reverse('avatar_view', args=['docent']))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)

    def test_google_login_is_not_started_by_a_plain_link(self):
        # Without SOCIALACCOUNT_LOGIN_ON_GET a GET only shows a confirmation page
        response = self.client.get('/accounts/google/login/')
        self.assertEqual(response.status_code, 200)

    def test_password_login_is_locked_after_repeated_failures(self):
        url = reverse('login')
        for _ in range(5):
            self.client.post(url, {'username': 'docent', 'password': 'wrong'})
        response = self.client.post(url, {'username': 'docent', 'password': 'correct-password'})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_client_ip_uses_the_address_added_by_the_proxy(self):
        request = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 10.0.0.9', REMOTE_ADDR='10.0.0.1')
        self.assertEqual(client_ip(request), '10.0.0.9')
