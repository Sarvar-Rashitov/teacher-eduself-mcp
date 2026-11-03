from django.urls import path
from .views import CreateSessionView, JoinSessionView, SessionStateView, SessionDetailView

app_name = 'live_sessions'

urlpatterns = [
    path('create/', CreateSessionView.as_view(), name='session-create'),
    path('join/', JoinSessionView.as_view(), name='session-join'),
    path('<str:room_code>/', SessionDetailView.as_view(), name='session-detail'),
    path('<str:room_code>/state/', SessionStateView.as_view(), name='session-state'),
]
