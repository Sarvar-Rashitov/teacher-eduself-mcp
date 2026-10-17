# ============================================================
# EduSelf Teacher — apps/mcp_server/oauth_urls.py
# Root OAuth 2.1 Endpoints (/oauth/...)
# ============================================================
from django.urls import path
from apps.mcp_server.views import OAuthAuthorizeView, OAuthTokenView

app_name = 'mcp_oauth'

urlpatterns = [
    path('authorize/', OAuthAuthorizeView.as_view(), name='authorize'),
    path('authorize', OAuthAuthorizeView.as_view(), name='authorize_no_slash'),
    path('token/', OAuthTokenView.as_view(), name='token'),
    path('token', OAuthTokenView.as_view(), name='token_no_slash'),
]
