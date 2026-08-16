from rest_framework import serializers
from .models import Conversation, Message, Source, ExternalContact, CannedReply


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # FK primary keys are UUID objects; JSON can encode them, msgpack cannot.
        for key in ('id', 'conversation', 'source', 'sender_internal_user'):
            value = data.get(key)
            if value is not None:
                data[key] = str(value)
        return data


class ConversationSerializer(serializers.ModelSerializer):
    # Return messages ordered by created_at so consumers always get chronological order
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = '__all__'

    def get_messages(self, obj):
        qs = obj.messages.order_by('created_at')
        return MessageSerializer(qs, many=True).data


class WebhookSerializer(serializers.Serializer):
    external_message_id = serializers.CharField(required=False, allow_blank=True)
    external_user_id = serializers.CharField()
    timestamp = serializers.CharField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    thread_id = serializers.CharField(required=False, allow_blank=True)
    raw = serializers.DictField(child=serializers.JSONField(), required=False)


class CannedReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = CannedReply
        fields = ('id', 'title', 'body', 'sort_order', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('id') is not None:
            data['id'] = str(data['id'])
        return data
