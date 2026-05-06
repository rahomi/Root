import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# load SECRET_KEY from environment variable
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

def _csv_env(name, default=""):
    return [
        value.strip()
        for value in os.getenv(name, default).split(",")
        if value.strip()
    ]


ALLOWED_HOSTS = _csv_env("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "")


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # cross-origin requests for local Flutter web testing
    'corsheaders',

    # rest framework
    'rest_framework',
    # jwt authentication
    'rest_framework_simplejwt',
    # enable logout blacklisting
    "rest_framework_simplejwt.token_blacklist",

    # load custom apps
    'accounts',
    'permissions',
    'members',
    'audit',
    'submissions',
    'ledger',
    'investments',
    'distributions',
    'snapshots',
    'reports',

]

# Set custom user model
AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = [
    'accounts.backends.RootPermissionBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOWED_ORIGINS = _csv_env("CORS_ALLOWED_ORIGINS")
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
]

ROOT_URLCONF = 'rootBackend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'rootBackend.wsgi.application'

# REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # All endpoints require authentication unless explicitly overridden
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",  # for file uploads
    ],
    "EXCEPTION_HANDLER": "accounts.exceptions.custom_exception_handler",
}

# Simple JWT configuration
SIMPLE_JWT = {
    # Access token: short-lived, used with every API call
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=30),
 
    # Refresh token: longer-lived, used only to get a new access token
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
 
    # Rotate refresh token on every use — old one is blacklisted automatically
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": True,
 
    # Signing
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
 
    # Header format: Authorization: Bearer <token>
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
 
    # Claims — user_id is the UUID PK
    "USER_ID_FIELD": "user_id",
    "USER_ID_CLAIM": "user_id",
 
    # Token classes
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

# Database connection to POSTGRESQL, load database credentials from .env
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'

MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

ATTACHMENT_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ATTACHMENT_ALLOWED_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
]
