# apps/authentication/urls.py
from django.urls import path
from .views import (
    LoginView,
    LogoutView,
    TelegramAuthCallbackView,
    GoogleAuthCallbackView,
    CurrentUserView,
)

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('telegram/callback/', TelegramAuthCallbackView.as_view(), name='telegram_callback'),
    path('google/callback/', GoogleAuthCallbackView.as_view(), name='google_callback'),
    path('me/', CurrentUserView.as_view(), name='current_user'),
]
