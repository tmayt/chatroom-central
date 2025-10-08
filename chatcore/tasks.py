from celery import shared_task
import requests

from .models import Message, DeliveryReceipt


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def send_outbound_message(self, message_id):
    try:
        msg = Message.objects.get(pk=message_id)
    except Message.DoesNotExist:
        return

    # build a simple payload
    payload = {
        'conversation_id': str(msg.conversation_id),
        'external_user_id': msg.conversation.external_contact.external_id if msg.conversation.external_contact else None,
        'content': msg.content,
        'message_id': str(msg.id),
    }

    endpoint = msg.source.outbound_endpoint_template
    headers = {'Content-Type': 'application/json'}
    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        msg.status = Message.STATUS_SENT
        msg.save()
        DeliveryReceipt.objects.create(message=msg, status='SENT', provider_response={'status_code': resp.status_code})
    except Exception as exc:
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            msg.status = Message.STATUS_FAILED
            msg.error_text = str(exc)
            msg.save()
            DeliveryReceipt.objects.create(message=msg, status='FAILED', provider_response={'error': str(exc)})
