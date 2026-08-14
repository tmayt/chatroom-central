import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework.authtoken.models import Token


class AdminConsumer(AsyncWebsocketConsumer):
    """Authenticated admin WebSocket for realtime conversation updates."""

    async def connect(self):
        self.user = await self._authenticate()
        if not self.user or not self.user.is_staff:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add('admin_updates', self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'connected'}))

    async def disconnect(self, close_code):
        if hasattr(self, 'channel_name'):
            await self.channel_layer.group_discard('admin_updates', self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients may send ping; respond with pong for keepalive.
        if text_data:
            try:
                data = json.loads(text_data)
            except json.JSONDecodeError:
                return
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

    async def chat_event(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def _authenticate(self):
        query = parse_qs(self.scope.get('query_string', b'').decode())
        token_key = (query.get('token') or [''])[0]
        if not token_key:
            return None
        try:
            token = Token.objects.select_related('user').get(key=token_key)
        except Token.DoesNotExist:
            return None
        return token.user if token.user.is_active else None
