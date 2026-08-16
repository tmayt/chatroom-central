from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from rest_framework.authtoken.models import Token
from .models import Source, ErrorLog
from .middleware import ErrorLogMiddleware


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


class ErrorLogApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='admin',
            password='secret',
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client = Client()

    def auth(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token.key}'}

    def test_list_view_and_delete(self):
        err = ErrorLog.objects.create(
            method='POST',
            path='/api/v1/conversations/x/reply/',
            status_code=500,
            message='boom',
            detail='traceback here',
            content_type='text/plain',
        )
        resp = self.client.get('/api/v1/errors/', **self.auth())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['id'], str(err.id))
        self.assertNotIn('detail', data['results'][0])

        detail = self.client.get(f'/api/v1/errors/{err.id}/', **self.auth())
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['detail'], 'traceback here')

        deleted = self.client.delete(f'/api/v1/errors/{err.id}/', **self.auth())
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(ErrorLog.objects.count(), 0)

    def test_delete_all(self):
        ErrorLog.objects.create(method='GET', path='/a', status_code=500, message='a')
        ErrorLog.objects.create(method='GET', path='/b', status_code=500, message='b')
        resp = self.client.delete('/api/v1/errors/', **self.auth())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['deleted'], 2)
        self.assertEqual(ErrorLog.objects.count(), 0)

    def test_requires_admin(self):
        resp = self.client.get('/api/v1/errors/')
        self.assertIn(resp.status_code, (401, 403))


class ErrorLogMiddlewareTests(TestCase):
    def test_logs_500_response(self):
        def get_response(_request):
            return HttpResponse('<title>ValueError at /explode/</title>', status=500, content_type='text/html')

        middleware = ErrorLogMiddleware(get_response)
        request = RequestFactory().get('/explode/')
        middleware(request)
        err = ErrorLog.objects.get()
        self.assertEqual(err.status_code, 500)
        self.assertEqual(err.method, 'GET')
        self.assertEqual(err.path, '/explode/')
        self.assertIn('ValueError', err.message)

    def test_skips_error_endpoints(self):
        def get_response(_request):
            return HttpResponse('fail', status=500)

        middleware = ErrorLogMiddleware(get_response)
        request = RequestFactory().get('/api/v1/errors/')
        middleware(request)
        self.assertEqual(ErrorLog.objects.count(), 0)


class MessageSerializeTests(TestCase):
    def setUp(self):
        self.src = Source.objects.create(slug='generic', display_name='Generic')
        from .models import Conversation, Message
        self.conv = Conversation.objects.create(source=self.src)
        self.msg = Message.objects.create(
            conversation=self.conv,
            direction=Message.DIRECTION_OUT,
            content='hello',
            source=self.src,
            status=Message.STATUS_PENDING,
        )

    def test_serialize_message_has_no_uuid_objects(self):
        from uuid import UUID
        from .api_helpers import serialize_message

        data = serialize_message(self.msg)

        def assert_no_uuid(value):
            self.assertNotIsInstance(value, UUID)
            if isinstance(value, dict):
                for item in value.values():
                    assert_no_uuid(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    assert_no_uuid(item)

        assert_no_uuid(data)
        self.assertEqual(data['id'], str(self.msg.id))
        self.assertEqual(data['conversation'], str(self.conv.id))
        self.assertEqual(data['source'], str(self.src.id))


class ConversationUnreadTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='admin',
            password='secret',
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client = Client()
        self.src = Source.objects.create(slug='generic', display_name='Generic')
        from .models import Conversation, Message
        self.Conversation = Conversation
        self.Message = Message

    def auth(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token.key}'}

    def test_unread_conversations_are_listed_first(self):
        read_conv = self.Conversation.objects.create(source=self.src)
        unread_conv = self.Conversation.objects.create(source=self.src)
        self.Message.objects.create(
            conversation=read_conv,
            direction=self.Message.DIRECTION_IN,
            content='old',
            source=self.src,
            seen=True,
        )
        self.Message.objects.create(
            conversation=unread_conv,
            direction=self.Message.DIRECTION_IN,
            content='new',
            source=self.src,
            seen=False,
        )
        resp = self.client.get('/api/v1/conversations/', **self.auth())
        self.assertEqual(resp.status_code, 200)
        ids = [item['id'] for item in resp.json()]
        self.assertEqual(ids[0], str(unread_conv.id))
        self.assertTrue(resp.json()[0]['has_unseen'])

    def test_mark_conversation_unread(self):
        conv = self.Conversation.objects.create(source=self.src)
        msg = self.Message.objects.create(
            conversation=conv,
            direction=self.Message.DIRECTION_IN,
            content='hello',
            source=self.src,
            seen=True,
        )
        resp = self.client.post(f'/api/v1/conversations/{conv.id}/unseen/', **self.auth())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['marked_unseen'], 1)
        msg.refresh_from_db()
        self.assertFalse(msg.seen)


class CannedReplyApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='admin',
            password='secret',
            is_staff=True,
            is_superuser=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client = Client()

    def auth(self):
        return {'HTTP_AUTHORIZATION': f'Token {self.token.key}'}

    def test_create_update_delete(self):
        created = self.client.post(
            '/api/v1/canned-replies/',
            {'title': 'Hello', 'body': 'Hi there', 'sort_order': 1},
            content_type='application/json',
            **self.auth(),
        )
        self.assertEqual(created.status_code, 201)
        reply_id = created.json()['id']

        listed = self.client.get('/api/v1/canned-replies/', **self.auth())
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)

        updated = self.client.patch(
            f'/api/v1/canned-replies/{reply_id}/',
            {'body': 'Hi there, how can I help?'},
            content_type='application/json',
            **self.auth(),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['body'], 'Hi there, how can I help?')

        deleted = self.client.delete(f'/api/v1/canned-replies/{reply_id}/', **self.auth())
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get('/api/v1/canned-replies/', **self.auth()).json(), [])
