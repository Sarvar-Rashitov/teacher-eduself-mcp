# apps/live_sessions/urls.py
from django.urls import path
from .views import CreateSessionView, JoinSessionView, SessionDetailView

app_name = 'live_sessions'

urlpatterns = [
    path('', CreateSessionView.as_view(), name='create'),
    path('join/', JoinSessionView.as_view(), name='join'),
    path('<str:room_code>/', SessionDetailView.as_view(), name='detail'),
]
