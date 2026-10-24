from django.urls import path
from .views import (
    telegram_auth_callback,
    google_auth_init,
    google_auth_callback,
    login_view,
    logout_view,
    me_view,
)

app_name = "authentication"

urlpatterns = [
    path("telegram/callback/", telegram_auth_callback, name="telegram_callback"),
    path("google/init/", google_auth_init, name="google_init"),
    path("google/callback/", google_auth_callback, name="google_callback"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("me/", me_view, name="me"),
]
