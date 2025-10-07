import hmac
import hashlib
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Source, WebhookEvent, ExternalContact, Conversation, Message
from .serializers import WebhookSerializer, ConversationSerializer
from rest_framework import generics
from rest_framework.permissions import IsAdminUser, BasePermission
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.response import Response as DRFResponse
from rest_framework import status as drf_status


class ConversationListView(generics.ListAPIView):
    queryset = Conversation.objects.all().order_by('-updated_at')
    serializer_class = None  # we'll return simplified JSON

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset().select_related('external_contact', 'source')
        # if ?mine=1 is provided, filter to conversations where the requesting
        # user is a participant. This enables a per-user chatroom view.
        if request.query_params.get('mine') in ('1', 'true', 'True') and request.user.is_authenticated:
            qs = qs.filter(participants=request.user)
        qs = qs[:100]
        data = []
        for c in qs:
            last = c.messages.order_by('-created_at').first()
            data.append({
                'id': str(c.id),
                'source': c.source.slug,
                'external_contact': c.external_contact.external_id if c.external_contact else None,
                'last_message': last.content if last else None,
                'updated_at': c.updated_at,
            })
        return DRFResponse(data)


class AdminOrFrontendTokenPermission(BasePermission):
    """Allow access if user is admin (session) OR request has matching X-API-KEY header.

    This is intentionally simple for local development. Replace with a stronger
    authentication mechanism for production.
    """
    def has_permission(self, request, view):
        # admin session user
        if request.user and request.user.is_authenticated and request.user.is_staff:
            return True
        # header token
        token = request.headers.get('X-API-KEY') or request.META.get('HTTP_X_API_KEY')
        expected = getattr(settings, 'FRONTEND_API_KEY', None)
        return bool(token and expected and token == expected)


class ReplyCreateView(APIView):
    # Use DRF authentication (Token or Session). Limit to admin users only for
    # now so replies must come from staff accounts or a token tied to a staff user.
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
        )
        # enqueue send task
        try:
            from .tasks import send_outbound_message
            send_outbound_message.delay(str(msg.id))
        except Exception:
            pass
        return DRFResponse({'id': str(msg.id), 'status': msg.status})



def verify_signature(secret: str, body: bytes, header_signature: str) -> bool:
    if not secret:
        return True
    try:
        scheme, sig = header_signature.split('=', 1)
    except Exception:
        return False
    if scheme.lower() != 'sha256':
        return False
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), sig)


def normalize_payload(data: dict) -> dict:
    # Minimal normalization: assume input has fields we defined in serializer
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
        # idempotency check
        if ext_id and Message.objects.filter(source=source, external_message_id=ext_id).exists():
            return Response({'status': 'duplicate'}, status=status.HTTP_200_OK)

        contact, _ = ExternalContact.objects.get_or_create(source=source, external_id=normalized['external_user_id'], defaults={'display_name': None})

        # find or create conversation by thread_id
        conv = None
        thread_id = normalized.get('thread_id')
        if thread_id:
            conv = Conversation.objects.filter(source=source, metadata__thread_id=thread_id).first()
        if not conv:
            conv = Conversation.objects.create(source=source, external_contact=contact)

        Message.objects.create(
            conversation=conv,
            direction=Message.DIRECTION_IN,
            sender_name=contact.display_name,
            content=normalized.get('content'),
            external_message_id=ext_id,
            source=source,
            status=Message.STATUS_RECEIVED,
            attachments=normalized.get('raw', {}).get('attachments', []),
        )

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class MockProviderReceiveView(APIView):
    """A simple endpoint that acts like an external provider receiving outbound replies.

    This is used for local testing: set a Source.outbound_endpoint_template to
    http://web:8000/api/mock/provider/receive/ so outbound messages are posted here.
    """

    def post(self, request):
        # Log to stdout so it appears in container logs
        print('--- Mock provider received payload ---')
        print(request.data)
        print('-------------------------------------')
        # Optionally persist as a WebhookEvent for auditing
        try:
            src = Source.objects.first()
            WebhookEvent.objects.create(source=src, raw_payload=request.data, headers=dict(request.headers))
        except Exception:
            pass
        return Response({'received': True}, status=status.HTTP_200_OK)


class ConversationDetailView(generics.RetrieveAPIView):
    """Return a conversation including its messages (read-only)."""
    queryset = Conversation.objects.all().select_related('external_contact', 'source')
    serializer_class = ConversationSerializer

