from rest_framework import serializers
from .models import Conversation, Message, Source, ExternalContact


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = '__all__'


class WebhookSerializer(serializers.Serializer):
    external_message_id = serializers.CharField(required=False, allow_blank=True)
    external_user_id = serializers.CharField()
    timestamp = serializers.CharField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    thread_id = serializers.CharField(required=False, allow_blank=True)
    raw = serializers.DictField(child=serializers.JSONField(), required=False)
