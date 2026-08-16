from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    ConversationListView,
    ReplyCreateView,
    ConversationDetailView,
    MessageSeenView,
    ConversationSeenView,
    ErrorLogListView,
    ErrorLogDetailView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversations-list'),
    path('conversations/<uuid:conversation_id>/reply/', ReplyCreateView.as_view(), name='conversation-reply'),
    path('conversations/<uuid:conversation_id>/seen/', ConversationSeenView.as_view(), name='conversation-seen'),
    path('conversations/<uuid:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('auth/token/', obtain_auth_token, name='api-token-auth'),
    path('messages/<uuid:message_id>/seen/', MessageSeenView.as_view(), name='message-seen'),
    path('errors/', ErrorLogListView.as_view(), name='error-log-list'),
    path('errors/<uuid:pk>/', ErrorLogDetailView.as_view(), name='error-log-detail'),
]
