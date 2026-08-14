import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# load .env from project root (if present)
load_dotenv(BASE_DIR / '.env')

# SECURITY: prefer environment-provided secret key
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret')

# DEBUG controlled by env (default False for safety)
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('1', 'true', 'yes')

# Public site URL (used for CSRF, CORS, and absolute links in integrations)
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:8000').rstrip('/')
_site = urlparse(SITE_URL)
SITE_HOST = _site.hostname or 'localhost'

# ALLOWED_HOSTS: comma-separated; defaults to SITE_URL hostname + local dev hosts
_allowed_hosts_raw = os.environ.get('DJANGO_ALLOWED_HOSTS', '').strip()
if _allowed_hosts_raw:
    ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_raw.split(',') if h.strip()]
else:
    ALLOWED_HOSTS = list(dict.fromkeys([SITE_HOST, 'localhost', '127.0.0.1']))

# CSRF trusted origins: SITE_URL plus http/https variants for each allowed host
CSRF_TRUSTED_ORIGINS = []
for origin in (SITE_URL,):
    if origin and origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)
for host in ALLOWED_HOSTS:
    for scheme in ('https', 'http'):
        origin = f'{scheme}://{host}'
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'rest_framework',
    'drf_spectacular',
    'chatcore',
    'corsheaders',
    'rest_framework.authtoken',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ]},
    }
]

WSGI_APPLICATION = 'project.wsgi.application'
ASGI_APPLICATION = 'project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.environ.get('CHANNEL_LAYERS_REDIS', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'))],
        },
    },
}

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DJANGO_DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DJANGO_DB_NAME', BASE_DIR / 'db.sqlite3'),
        'USER': os.environ.get('DJANGO_DB_USER', ''),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
        'HOST': os.environ.get('DJANGO_DB_HOST', ''),
        'PORT': os.environ.get('DJANGO_DB_PORT', ''),
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Let WhiteNoise serve compressed files and add caching headers
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')

# allow local frontend dev + deployed site origin
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    SITE_URL,
]
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(CORS_ALLOWED_ORIGINS))

CORS_ALLOW_CREDENTIALS = True

# A simple API key used by the local frontend to authenticate reply requests.
# In production you should replace this with a proper auth flow (session, JWT, OAuth).
FRONTEND_API_KEY = os.environ.get('FRONTEND_API_KEY', 'dev-frontend-token')

# REST framework settings: enable TokenAuthentication (and keep SessionAuth for admin UI).
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # default permission can remain permissive; views opt-in to stricter checks.
}

# drf-spectacular settings (minimal)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Chatroom API',
    'DESCRIPTION': 'API for Chatroom admin and webhook integrations',
    'VERSION': '1.0.0',
    'SERVERS': [{'url': SITE_URL, 'description': 'Current deployment'}],
}
