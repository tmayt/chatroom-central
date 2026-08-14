"""Helpers for broadcasting realtime events to connected admin clients."""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


ADMIN_GROUP = 'admin_updates'


def broadcast_admin_event(event_type, payload=None):
    """Send an event to all connected admin WebSocket clients."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    data = {'type': event_type}
    if payload:
        data.update(payload)
    async_to_sync(channel_layer.group_send)(
        ADMIN_GROUP,
        {
            'type': 'chat.event',
            'data': data,
        },
    )
