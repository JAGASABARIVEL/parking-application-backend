# ==================== PARKING_BACKEND/SETTINGS.PY ====================
import os
from pathlib import Path
from datetime import timedelta
from decouple import config

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='your-secret-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
GDAL_LIBRARY_PATH = "/lib/x86_64-linux-gnu/libgdal.so"

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'django_celery_beat',
    
    # Local apps
    'users',
    'parking',
    'bookings',
    'payments',
    'disputes'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'parking_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'parking_backend.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='parking_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter'
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', 
                              default='http://localhost:8000, http://localhost:8100,http://localhost:3000').split(',')
CORS_ALLOW_CREDENTIALS = True

# Razorpay Configuration
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')
RAZORPAY_WEBHOOK_SECRET = config('RAZORPAY_WEBHOOK_SECRET', default='')

# Email Configuration (for notifications)
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Firebase Configuration (for notifications)
FIREBASE_API_KEY = config('FIREBASE_API_KEY', default='')

LOG_DIR = BASE_DIR / 'logs'
os.makedirs(LOG_DIR, exist_ok=True)
# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'debug.log'),
            'formatter': 'verbose'
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CELERY_BEAT_SCHEDULE = {
    'settle-cod-payments': {
        'task': 'payments.tasks.settle_pending_cod_payments',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
    'block-owners-overdue': {
        'task': 'payments.tasks.auto_block_owners_with_overdue_dues',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    'send-due-notifications': {
        'task': 'payments.tasks.send_commission_due_notifications',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10 AM
    },
    'reconcile-payments': {
        'task': 'payments.tasks.reconcile_razorpay_payments',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'check-refund-status': {
        'task': 'payments.tasks.check_refund_status',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}



# ==================== MANAGE.PY COMMANDS ====================
"""
Run these commands to set up the project:

1. Create virtual environment:
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

2. Install requirements:
   pip install -r requirements.txt

3. Create .env file with settings (copy from above)

4. Run migrations:
   python manage.py migrate
   
5. Create superuser:
   python manage.py createsuperuser

6. Create necessary directories:
   mkdir logs
   mkdir media

7. Run development server:
   python manage.py runserver

8. Access admin panel:
   http://localhost:8000/admin/

9. API endpoints will be available at:
   http://localhost:8000/api/v1/
"""


# ==================== API ENDPOINTS SUMMARY ====================
"""
AUTHENTICATION ENDPOINTS:
POST   /api/v1/auth/register/                    - Register new user
POST   /api/v1/auth/login/                       - User login
GET    /api/v1/auth/profile/                     - Get user profile
PUT    /api/v1/auth/profile/                     - Update user profile
POST   /api/v1/auth/token/                       - Get JWT token
POST   /api/v1/auth/token/refresh/               - Refresh JWT token

VEHICLE MANAGEMENT:
GET    /api/v1/vehicles/                         - List user's vehicles
POST   /api/v1/vehicles/                         - Register new vehicle
GET    /api/v1/vehicles/{id}/                    - Get vehicle details
PUT    /api/v1/vehicles/{id}/                    - Update vehicle
DELETE /api/v1/vehicles/{id}/                    - Delete vehicle
GET    /api/v1/vehicles/active_vehicles/         - Get active vehicles only

PARKING SPACES (OWNER):
GET    /api/v1/parking-spaces/                   - List all parking spaces
POST   /api/v1/parking-spaces/                   - Create parking space
GET    /api/v1/parking-spaces/{id}/              - Get space details
PUT    /api/v1/parking-spaces/{id}/              - Update parking space
DELETE /api/v1/parking-spaces/{id}/              - Delete parking space
GET    /api/v1/parking-spaces/my_spaces/         - Get owner's spaces
GET    /api/v1/parking-spaces/{id}/owner_stats/  - Get space statistics
POST   /api/v1/parking-spaces/{id}/update_status/  - Update space status
GET    /api/v1/parking-spaces/{id}/availability_slots/  - Get available slots

PARKING SPACES (SEARCH):
GET    /api/v1/parking-spaces/nearby/?lat=X&lng=Y&radius=5  - Nearby spaces
GET    /api/v1/parking-spaces/?city=CityName               - Filter by city
GET    /api/v1/parking-spaces/?space_type=garage           - Filter by type
GET    /api/v1/parking-spaces/?search=landmark             - Search spaces

BOOKINGS (DRIVER):
POST   /api/v1/bookings/                         - Create booking
GET    /api/v1/bookings/                         - List bookings
GET    /api/v1/bookings/{id}/                    - Get booking details
POST   /api/v1/bookings/{id}/update_status/     - Update booking status
POST   /api/v1/bookings/{id}/cancel_booking/    - Cancel booking
PUT    /api/v1/bookings/{id}/update_location/   - Update location (tracking)
GET    /api/v1/bookings/my_bookings/             - Get my bookings
POST   /api/v1/bookings/{id}/confirm_booking/   - Confirm after payment

BOOKINGS (OWNER):
GET    /api/v1/bookings/my_space_bookings/      - Get all bookings for owned spaces
GET    /api/v1/bookings/{id}/tracking_info/     - Real-time vehicle tracking

REVIEWS:
POST   /api/v1/reviews/create_review/           - Create review for booking
GET    /api/v1/reviews/                         - List reviews

PAYMENTS:
POST   /api/v1/payments/initiate/               - Initiate payment
POST   /api/v1/payments/verify/                 - Verify Razorpay payment
GET    /api/v1/payments/status/?booking_id=X    - Get payment status


REQUEST/RESPONSE EXAMPLES:

1. USER REGISTRATION:
POST /api/v1/auth/register/
{
    "username": "john_driver",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+919876543210",
    "user_type": "driver",
    "password": "securepassword123",
    "password_confirm": "securepassword123"
}

2. REGISTER VEHICLE:
POST /api/v1/vehicles/
{
    "vehicle_number": "DL01AB1234",
    "vehicle_type": "Car",
    "vehicle_model": "Honda City",
    "vehicle_color": "Silver",
    "dl_number": "DL1234567890",
    "dl_expiry_date": "2025-12-31",
    "vehicle_registration_number": "DL-01-AB-1234",
    "length_in_meters": 4.5,
    "height_in_meters": 1.6,
    "width_in_meters": 1.8,
    "vehicle_document": <file>,
    "dl_document": <file>
}

3. CREATE PARKING SPACE:
POST /api/v1/parking-spaces/
{
    "title": "Secure Garage Near Metro",
    "description": "24x7 covered parking with surveillance",
    "address": "123 Main Street",
    "city": "Delhi",
    "area": "Connaught Place",
    "landmark": "Near Metro Station",
    "location": "28.6139,77.2090",
    "space_type": "garage",
    "total_spaces": 5,
    "available_spaces": 5,
    "price_per_day": 500,
    "price_per_week": 3000,
    "price_per_month": 10000,
    "price_per_year": 100000,
    "max_vehicle_height": 2.0,
    "max_vehicle_length": 5.0,
    "max_vehicle_width": 2.0,
    "allowed_vehicle_types": ["car", "suv"],
    "has_security_camera": true,
    "has_lighting": true,
    "has_ev_charging": false,
    "has_surveillance": true,
    "has_covered": true,
    "has_24_7_access": true,
    "available_from": "06:00:00",
    "available_until": "23:00:00",
    "accepted_payment_methods": ["razorpay", "cod"],
    "image": <file>
}

4. CREATE BOOKING:
POST /api/v1/bookings/
{
    "parking_space": 1,
    "vehicle_id": 1,
    "booking_type": "daily",
    "start_datetime": "2025-10-27T10:00:00Z",
    "end_datetime": "2025-10-28T10:00:00Z",
    "special_instructions": "Please keep away from other vehicles"
}

5. INITIATE PAYMENT:
POST /api/v1/payments/initiate/
{
    "booking_id": 1,
    "payment_method": "razorpay"
}

6. VERIFY RAZORPAY PAYMENT:
POST /api/v1/payments/verify/
{
    "razorpay_order_id": "order_1234567890",
    "razorpay_payment_id": "pay_1234567890",
    "razorpay_signature": "signature_hash"
}

7. UPDATE LOCATION (Real-time tracking):
PUT /api/v1/bookings/1/update_location/
{
    "current_latitude": 28.6139,
    "current_longitude": 77.2090,
    "distance_remaining": 2.5,
    "eta_minutes": 15
}

8. CREATE REVIEW:
POST /api/v1/reviews/create_review/
{
    "booking_id": 1,
    "rating": 5,
    "comment": "Great parking space, very clean and secure",
    "tags": ["clean", "safe", "convenient"]
}
"""