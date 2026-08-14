from django.urls import re_path

from .consumers import AdminConsumer

websocket_urlpatterns = [
    re_path(r'ws/admin/$', AdminConsumer.as_asgi()),
]
