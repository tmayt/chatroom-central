import uuid
from django.db import models
from django.contrib.auth import get_user_model


class Source(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    display_name = models.CharField(max_length=200)
    inbound_secret = models.CharField(max_length=200, null=True, blank=True)
    outbound_endpoint_template = models.CharField(max_length=1000, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class ExternalContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=500)
    display_name = models.CharField(max_length=200, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('source', 'external_id')

    def __str__(self):
        return f"{self.display_name or self.external_id} @ {self.source.slug}"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    external_contact = models.ForeignKey(ExternalContact, null=True, blank=True, on_delete=models.SET_NULL)
    # participants: internal users who are part of the conversation (for per-user chatrooms)
    participants = models.ManyToManyField(get_user_model(), blank=True, related_name='conversations')
    title = models.CharField(max_length=500, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_closed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or str(self.id)


class Message(models.Model):
    DIRECTION_IN = 'IN'
    DIRECTION_OUT = 'OUT'
    DIRECTION_CHOICES = [(DIRECTION_IN, 'Inbound'), (DIRECTION_OUT, 'Outbound')]

    STATUS_RECEIVED = 'RECEIVED'
    STATUS_PENDING = 'PENDING'
    STATUS_SENT = 'SENT'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PENDING, 'Pending Send'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    sender_name = models.CharField(max_length=200, null=True, blank=True)
    sender_internal_user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)
    content = models.TextField(null=True, blank=True)
    external_message_id = models.CharField(max_length=500, null=True, blank=True)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    error_text = models.TextField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'external_message_id'], name='unique_external_message_id', condition=models.Q(external_message_id__isnull=False))
        ]

    def __str__(self):
        return f"{self.direction} {self.content[:40]}"


class DeliveryReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='delivery_receipts')
    status = models.CharField(max_length=50)
    provider_response = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)


class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    raw_payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
