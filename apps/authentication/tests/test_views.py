import time
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.authentication.tests.test_telegram_auth import (
    generate_valid_telegram_payload,
    TEST_BOT_TOKEN
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username='teacher_john',
        email='john@example.com',
        password='Password123!',
        role='teacher',
        first_name='John',
        last_name='Doe'
    )


@pytest.mark.django_db
class TestAuthViews:
    def test_login_success_with_username(self, api_client, test_user):
        url = reverse('authentication:login')
        response = api_client.post(url, {
            'username': 'teacher_john',
            'password': 'Password123!'
        }, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
        assert response.data['user']['username'] == 'teacher_john'
        assert response.data['user']['role'] == 'teacher'

    def test_login_success_with_email(self, api_client, test_user):
        url = reverse('authentication:login')
        response = api_client.post(url, {
            'email': 'john@example.com',
            'password': 'Password123!'
        }, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
        assert response.data['user']['email'] == 'john@example.com'

    def test_login_invalid_password(self, api_client, test_user):
        url = reverse('authentication:login')
        response = api_client.post(url, {
            'username': 'teacher_john',
            'password': 'WrongPassword'
        }, format='json')
        assert response.status_code == 401
        assert 'error' in response.data

    def test_logout(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('authentication:logout')
        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data['status'] == 'ok'

    def test_current_user_me(self, api_client, test_user):
        url = reverse('authentication:current_user')

        # Anonim so'rov 403 berishi kerak
        anon_response = api_client.get(url)
        assert anon_response.status_code == 403

        # Autentifikatsiyalangan so'rov 200 berishi kerak
        api_client.force_authenticate(user=test_user)
        auth_response = api_client.get(url)
        assert auth_response.status_code == 200
        assert auth_response.data['user']['id'] == str(test_user.id)


@pytest.mark.django_db
class TestTelegramAuthCallbackView:
    def test_telegram_callback_success(self, api_client, settings):
        settings.TELEGRAM_BOT_TOKEN = TEST_BOT_TOKEN
        raw_data = {
            'id': 11223344,
            'first_name': 'Zilola',
            'username': 'zilola_tg',
            'auth_date': int(time.time()),
        }
        payload = generate_valid_telegram_payload(raw_data, TEST_BOT_TOKEN)

        url = reverse('authentication:telegram_callback')
        response = api_client.post(url, payload, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
        assert response.data['user']['username'] == 'zilola_tg'
        assert User.objects.filter(telegram_id=11223344).exists()

    def test_telegram_callback_forged_hash_forbidden(self, api_client, settings):
        settings.TELEGRAM_BOT_TOKEN = TEST_BOT_TOKEN
        raw_data = {
            'id': 11223344,
            'first_name': 'Zilola',
            'username': 'zilola_tg',
            'auth_date': int(time.time()),
            'hash': 'invalid_forged_hash_value'
        }
        url = reverse('authentication:telegram_callback')
        response = api_client.post(url, raw_data, format='json')
        assert response.status_code == 403
        assert 'Soxta' in response.data['error']


@pytest.mark.django_db
class TestGoogleAuthCallbackView:
    def test_google_callback_success(self, api_client):
        user_info = {
            'email': 'google_teacher@example.com',
            'email_verified': True,
            'given_name': 'Anvar',
            'family_name': 'Sobirov',
            'picture': 'https://lh3.googleusercontent.com/pic'
        }
        url = reverse('authentication:google_callback')
        response = api_client.post(url, {'user_info': user_info}, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'ok'
        assert response.data['user']['email'] == 'google_teacher@example.com'
        assert User.objects.filter(email='google_teacher@example.com').exists()

    def test_google_callback_unverified_email_bad_request(self, api_client):
        user_info = {
            'email': 'unverified@example.com',
            'email_verified': False,
        }
        url = reverse('authentication:google_callback')
        response = api_client.post(url, {'user_info': user_info}, format='json')
        assert response.status_code == 400
        assert 'verified' in response.data['error']
