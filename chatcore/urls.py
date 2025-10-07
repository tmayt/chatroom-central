from django.urls import path
from .views import IncomingWebhookView

from .views import MockProviderReceiveView

urlpatterns = [
    path('webhooks/<slug:source_slug>/incoming/', IncomingWebhookView.as_view(), name='incoming-webhook'),
    path('mock/provider/receive/', MockProviderReceiveView.as_view(), name='mock-provider-receive'),
]
