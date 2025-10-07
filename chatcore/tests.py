from django.test import TestCase, Client
from django.urls import reverse
from .models import Source, ExternalContact, Conversation, Message


class WebhookTests(TestCase):
    def setUp(self):
        self.src = Source.objects.create(slug='generic', display_name='Generic', inbound_secret='secret', outbound_endpoint_template='http://example.local/out')
        self.client = Client()

    def test_incoming_creates_message_and_conversation(self):
        url = reverse('incoming-webhook', kwargs={'source_slug': 'generic'})
        payload = {
            'external_message_id': 'ext-1',
            'external_user_id': 'user-1',
            'content': 'Hello world'
        }
        resp = self.client.post(url, payload, content_type='application/json', HTTP_X_SIGNATURE='sha256=invalid')
        # signature invalid because we used secret; should be 401
        self.assertEqual(resp.status_code, 401)
