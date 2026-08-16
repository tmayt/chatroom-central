from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Source, WebhookEvent, ExternalContact, Conversation, Message, ErrorLog
from .serializers import WebhookSerializer, ConversationSerializer
from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response as DRFResponse
from rest_framework import status as drf_status

from .api_helpers import (
    filter_conversations_for_user,
    get_conversation_queryset,
    serialize_conversation_summary,
    serialize_message,
)
from .realtime import broadcast_admin_event


class ConversationListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    queryset = Conversation.objects.all()
    serializer_class = None

    def list(self, request, *args, **kwargs):
        mine = request.query_params.get('mine') in ('1', 'true', 'True')
        qs = filter_conversations_for_user(get_conversation_queryset(), request.user, mine)
        data = [serialize_conversation_summary(c) for c in qs]
        return DRFResponse(data)


class ReplyCreateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, conversation_id):
        conv = get_object_or_404(Conversation, pk=conversation_id)
        text = request.data.get('text')
        if not text:
            return DRFResponse({'detail': 'text required'}, status=drf_status.HTTP_400_BAD_REQUEST)
        msg = Message.objects.create(
            conversation=conv,
            direction=Message.DIRECTION_OUT,
            content=text,
            source=conv.source,
            status=Message.STATUS_PENDING,
            sender_internal_user=request.user if request.user.is_authenticated else None,
        )
        conv.save(update_fields=['updated_at'])
        try:
            from .tasks import send_outbound_message
            send_outbound_message.delay(str(msg.id))
        except Exception:
            pass

        msg_data = serialize_message(msg)
        broadcast_admin_event('message.new', {
            'conversation_id': str(conv.id),
            'message': msg_data,
            'conversation': serialize_conversation_summary(
                get_conversation_queryset().get(pk=conv.id),
            ),
        })
        return DRFResponse({'id': str(msg.id), 'status': msg.status, 'message': msg_data})


def verify_signature(secret: str, body: bytes, header_signature: str) -> bool:
    if not secret:
        return True
    return header_signature.strip() == secret.strip()


def normalize_payload(data: dict) -> dict:
    return {
        'external_message_id': data.get('external_message_id'),
        'external_user_id': data.get('external_user_id'),
        'timestamp': data.get('timestamp'),
        'content': data.get('content'),
        'thread_id': data.get('thread_id'),
        'raw': data,
    }


class IncomingWebhookView(APIView):
    def post(self, request, source_slug):
        source = get_object_or_404(Source, slug=source_slug, is_active=True)
        raw_body = request.body
        sig_header = request.headers.get('X-Signature', '')
        if source.inbound_secret:
            if not verify_signature(source.inbound_secret, raw_body, sig_header):
                return Response({'detail': 'invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = WebhookSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        WebhookEvent.objects.create(source=source, raw_payload=request.data, headers=dict(request.headers))

        normalized = normalize_payload(serializer.validated_data)

        ext_id = normalized.get('external_message_id')
        if ext_id and Message.objects.filter(source=source, external_message_id=ext_id).exists():
            return Response({'status': 'duplicate'}, status=status.HTTP_200_OK)

        contact, _ = ExternalContact.objects.get_or_create(
            source=source,
            external_id=normalized['external_user_id'],
            defaults={'display_name': None},
        )

        conv = None
        thread_id = normalized.get('thread_id')
        if thread_id:
            conv = Conversation.objects.filter(source=source, metadata__thread_id=thread_id).first()
        if not conv:
            conv = Conversation.objects.create(source=source, metadata=normalized, external_contact=contact)

        msg = Message.objects.create(
            conversation=conv,
            direction=Message.DIRECTION_IN,
            sender_name=contact.display_name,
            content=normalized.get('content'),
            external_message_id=ext_id,
            source=source,
            status=Message.STATUS_RECEIVED,
            attachments=normalized.get('raw', {}).get('attachments', []),
        )
        conv.save(update_fields=['updated_at'])

        msg_data = serialize_message(msg)
        try:
            summary = serialize_conversation_summary(
                get_conversation_queryset().get(pk=conv.id),
            )
        except Conversation.DoesNotExist:
            summary = None

        broadcast_admin_event('message.new', {
            'conversation_id': str(conv.id),
            'message': msg_data,
            'conversation': summary,
        })
        return Response({'status': 'ok', 'message_id': str(msg.id)}, status=status.HTTP_200_OK)


class MockProviderReceiveView(APIView):
    def post(self, request):
        print('--- Mock provider received payload ---')
        print(request.data)
        print('-------------------------------------')
        try:
            src = Source.objects.first()
            WebhookEvent.objects.create(source=src, raw_payload=request.data, headers=dict(request.headers))
        except Exception:
            pass
        return Response({'received': True}, status=status.HTTP_200_OK)


class MessageSeenView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, message_id):
        msg = get_object_or_404(Message, pk=message_id)
        if not msg.seen:
            msg.seen = True
            msg.save(update_fields=['seen'])
            broadcast_admin_event('message.updated', {
                'conversation_id': str(msg.conversation_id),
                'message': serialize_message(msg),
            })
        return DRFResponse({'id': str(msg.id), 'seen': msg.seen})


class ConversationSeenView(APIView):
    """Mark all inbound unseen messages in a conversation as seen."""

    permission_classes = [IsAdminUser]

    def post(self, request, conversation_id):
        conv = get_object_or_404(Conversation, pk=conversation_id)
        updated = Message.objects.filter(
            conversation=conv,
            direction=Message.DIRECTION_IN,
            seen=False,
        ).update(seen=True)
        if updated:
            broadcast_admin_event('conversation.updated', {
                'conversation_id': str(conv.id),
            })
        return DRFResponse({'conversation_id': str(conv.id), 'marked_seen': updated})


class ConversationDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAdminUser]
    queryset = Conversation.objects.all().select_related('external_contact', 'source')
    serializer_class = ConversationSerializer


def serialize_error_log(err, include_detail=False):
    data = {
        'id': str(err.id),
        'method': err.method,
        'path': err.path,
        'status_code': err.status_code,
        'message': err.message,
        'content_type': err.content_type,
        'created_at': err.created_at.isoformat() if err.created_at else None,
    }
    if include_detail:
        data['detail'] = err.detail
    return data


class ErrorLogListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = ErrorLog.objects.all()
        total = qs.count()
        if request.query_params.get('count_only') in ('1', 'true', 'True'):
            return DRFResponse({'count': total})
        return DRFResponse({
            'count': total,
            'results': [serialize_error_log(err) for err in qs[:200]],
        })

    def delete(self, request):
        deleted, _ = ErrorLog.objects.all().delete()
        return DRFResponse({'deleted': deleted})


class ErrorLogDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        err = get_object_or_404(ErrorLog, pk=pk)
        return DRFResponse(serialize_error_log(err, include_detail=True))

    def delete(self, request, pk):
        err = get_object_or_404(ErrorLog, pk=pk)
        err.delete()
        return DRFResponse(status=drf_status.HTTP_204_NO_CONTENT)
