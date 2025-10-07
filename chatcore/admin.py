from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.utils.html import format_html

from .models import Source, ExternalContact, Conversation, Message, DeliveryReceipt, WebhookEvent


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('slug', 'display_name', 'is_active')


@admin.register(ExternalContact)
class ExternalContactAdmin(admin.ModelAdmin):
    list_display = ('external_id', 'display_name', 'source')


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('direction', 'sender_name', 'content', 'status', 'created_at')
    fields = ('direction', 'sender_name', 'content', 'status', 'created_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'external_contact', 'is_closed', 'updated_at')
    inlines = [MessageInline]

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('<path:object_id>/reply/', self.admin_site.admin_view(self.reply_view), name='chatcore_conversation_reply'),
        ]
        return my_urls + urls

    def reply_view(self, request, object_id):
        # very small convenience: create an outbound message from admin
        conv = Conversation.objects.get(pk=object_id)
        if request.method == 'POST':
            text = request.POST.get('text')
            Message.objects.create(conversation=conv, direction=Message.DIRECTION_OUT, content=text, source=conv.source, status=Message.STATUS_PENDING)
            return redirect('admin:chatcore_conversation_change', object_id)
        return format_html('<form method="post">{csrf}<textarea name="text" rows="4" cols="80"></textarea><br/><input type="submit" value="Send"/></form>', csrf="<input type='hidden' name='csrfmiddlewaretoken' value='{}'/>".format(request.COOKIES.get('csrftoken', '')))


@admin.register(DeliveryReceipt)
class DeliveryReceiptAdmin(admin.ModelAdmin):
    list_display = ('message', 'status', 'timestamp')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'processed', 'created_at')
