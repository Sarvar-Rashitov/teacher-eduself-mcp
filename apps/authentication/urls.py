from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Telegram Login Widget
    path('telegram/callback/', views.telegram_auth_callback, name='telegram_auth_callback'),

    # Google OAuth 2.0
    path('google/login/', views.google_auth_redirect, name='google_auth_redirect'),
    path('google/callback/', views.google_auth_callback, name='google_auth_callback'),

    # Standart sessiyali autentifikatsiya
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('me/', views.me_view, name='me'),
]
