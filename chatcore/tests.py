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
