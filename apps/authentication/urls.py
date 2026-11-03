"""
URL configuration for the authentication app.
"""

from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('telegram/', views.telegram_auth_callback, name='telegram_callback'),
    path('google/', views.google_auth_callback, name='google_callback'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('me/', views.me_view, name='me'),
]
