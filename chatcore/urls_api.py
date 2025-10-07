from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import ConversationListView, ReplyCreateView, ConversationDetailView

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversations-list'),
    path('conversations/<uuid:conversation_id>/reply/', ReplyCreateView.as_view(), name='conversation-reply'),
    path('conversations/<uuid:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    # simple token obtain endpoint: POST {username, password} -> {token}
    path('auth/token/', obtain_auth_token, name='api-token-auth'),
]
