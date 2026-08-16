"""Shared serialization helpers for API and realtime events."""

"""Shared serialization helpers for API and realtime events."""

import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, DateTimeField, Max, Q
from django.db.models.functions import Coalesce

from .models import Conversation, Message
from .serializers import MessageSerializer


def json_safe(value):
    """Convert UUID/datetime/etc. into JSON (and Redis msgpack) safe types."""
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def serialize_message(msg):
    return json_safe(MessageSerializer(msg).data)


def serialize_conversation_summary(c):
    """Build the list-item dict for a conversation (with annotations)."""
    last = c.messages.order_by('-created_at').first()
    return {
        'id': str(c.id),
        'source': c.source.slug,
        'external_contact': c.external_contact.external_id if c.external_contact else None,
        'last_message': last.content if last else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        'has_unseen': bool(getattr(c, 'unseen_count', 0)),
    }


def get_conversation_queryset():
    qs = Conversation.objects.all().select_related('external_contact', 'source')
    qs = qs.annotate(
        last_msg_time=Coalesce(Max('messages__created_at'), 'updated_at', output_field=DateTimeField()),
        unseen_count=Count('messages', filter=Q(messages__direction='IN') & (~Q(messages__seen=True))),
    )
    return qs.order_by('-last_msg_time')


def filter_conversations_for_user(qs, user, mine_only=False):
    if mine_only and user.is_authenticated:
        qs = qs.filter(participants=user)
    return qs[:100]
