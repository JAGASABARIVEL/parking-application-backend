# ==================== UTILS/DISTANCE_CALCULATOR.PY ====================
from geopy.distance import geodesic
from django.contrib.gis.geos import Point

class DistanceCalculator:
    """Calculate distance and ETA between two points"""
    
    @staticmethod
    def get_distance_km(lat1, lng1, lat2, lng2):
        """Get distance in kilometers"""
        coord1 = (lat1, lng1)
        coord2 = (lat2, lng2)
        return geodesic(coord1, coord2).km
    
    @staticmethod
    def calculate_eta(distance_km, avg_speed_kmh=40):
        """Calculate estimated time of arrival in minutes"""
        if distance_km == 0:
            return 0
        hours = distance_km / avg_speed_kmh
        return int(hours * 60)
    
    @staticmethod
    def update_booking_location_tracking(booking, current_lat, current_lng):
        """Update booking location and calculate ETA"""
        from .models import BookingLocation
        
        try:
            tracking = booking.location_tracking
            
            distance = DistanceCalculator.get_distance_km(
                current_lat, current_lng,
                tracking.destination_latitude,
                tracking.destination_longitude
            )
            
            eta = DistanceCalculator.calculate_eta(distance)
            
            tracking.current_latitude = current_lat
            tracking.current_longitude = current_lng
            tracking.distance_remaining = round(distance, 2)
            tracking.eta_minutes = eta
            
            if distance < 0.1:  # Less than 100 meters
                tracking.reached_destination = True
                tracking.reached_at = timezone.now()
            
            tracking.save()
            return tracking
        except Exception as e:
            logger.error(f"Error updating location: {str(e)}")
            return None













# ==================== REQUIREMENTS.TXT (COMPLETE) ====================
"""
Django==4.2.0
djangorestframework==3.14.0
djangorestframework-simplejwt==5.3.0
django-cors-headers==4.3.0
django-filter==23.5
psycopg2-binary==2.9.9
Pillow==10.1.0
django-environ==0.21.0
geopy==2.4.0
celery==5.3.4
redis==5.0.1
phonenumbers==8.13.0
django-phonenumber-field==7.2.0
razorpay==1.4.1
requests==2.31.0
gunicorn==21.2.0
whitenoise==6.6.0
"""


# ==================== DOCKER FILE ====================
"""
Create a Dockerfile for containerization:

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "parking_backend.wsgi:application"]


Create docker-compose.yml:

version: '3.8'

services:
  db:
    image: postgis/postgis:15-3.3
    environment:
      POSTGRES_DB: parking_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DEBUG=True
      - DB_NAME=parking_db
      - DB_USER=postgres
      - DB_PASSWORD=password
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery:
    build: .
    command: celery -A parking_backend worker -l info
    volumes:
      - .:/app
    environment:
      - DB_NAME=parking_db
      - DB_USER=postgres
      - DB_PASSWORD=password
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
"""


# ==================== MANAGEMENT COMMAND: CREATE DEFAULT DATA ====================
"""
Create file: apps/parking/management/commands/populate_initial_data.py

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.parking.models import ParkingSpace
from apps.users.models import CustomUser

class Command(BaseCommand):
    help = 'Populate initial parking spaces for testing'

    def handle(self, *args, **options):
        try:
            owner = CustomUser.objects.filter(user_type__in=['owner', 'both']).first()
            
            if not owner:
                self.stdout.write(self.style.ERROR('No parking owner found'))
                return
            
            spaces = [
                {
                    'title': 'Downtown Parking Garage',
                    'description': '24/7 secure underground parking with CCTV surveillance',
                    'address': '123 Main Street, Downtown',
                    'city': 'Delhi',
                    'area': 'Connaught Place',
                    'landmark': 'Near Metro Station',
                    'location': Point(77.2090, 28.6139),
                    'space_type': 'garage',
                    'total_spaces': 20,
                    'available_spaces': 20,
                    'price_per_day': 500,
                    'price_per_week': 3000,
                    'price_per_month': 10000,
                    'price_per_year': 100000,
                    'max_vehicle_height': 2.2,
                    'max_vehicle_length': 5.5,
                    'max_vehicle_width': 2.5,
                    'allowed_vehicle_types': '["car", "suv"]',
                    'has_security_camera': True,
                    'has_lighting': True,
                    'has_surveillance': True,
                    'has_covered': True,
                    'has_24_7_access': True,
                    'available_from': '00:00',
                    'available_until': '23:59',
                    'accepted_payment_methods': '["razorpay", "cod"]',
                },
                {
                    'title': 'Open Air Parking Lot',
                    'description': 'Spacious open parking with good ventilation',
                    'address': '456 Market Street',
                    'city': 'Delhi',
                    'area': 'Chandni Chowk',
                    'landmark': 'Near Shopping Mall',
                    'location': Point(77.2300, 28.6450),
                    'space_type': 'open',
                    'total_spaces': 50,
                    'available_spaces': 50,
                    'price_per_day': 300,
                    'price_per_week': 1800,
                    'price_per_month': 6000,
                    'price_per_year': 60000,
                    'max_vehicle_height': 2.5,
                    'max_vehicle_length': 6.0,
                    'max_vehicle_width': 2.8,
                    'allowed_vehicle_types': '["car", "suv", "bike"]',
                    'has_security_camera': True,
                    'has_lighting': False,
                    'has_surveillance': False,
                    'has_covered': False,
                    'has_24_7_access': False,
                    'available_from': '06:00',
                    'available_until': '23:00',
                    'accepted_payment_methods': '["razorpay"]',
                },
            ]
            
            for space_data in spaces:
                space, created = ParkingSpace.objects.get_or_create(
                    title=space_data['title'],
                    owner=owner,
                    defaults=space_data
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created: {space.title}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Already exists: {space.title}'))
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

Run with: python manage.py populate_initial_data
"""


# ==================== TESTING: SAMPLE UNIT TESTS ====================
"""
Create file: tests/test_parking.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.parking.models import ParkingSpace
from django.contrib.gis.geos import Point

User = get_user_model()

class ParkingSpaceTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='owner1',
            email='owner@test.com',
            password='testpass123',
            phone_number='+919876543210',
            user_type='owner'
        )
        
        self.driver = User.objects.create_user(
            username='driver1',
            email='driver@test.com',
            password='testpass123',
            phone_number='+919876543211',
            user_type='driver'
        )
    
    def test_owner_can_create_parking_space(self):
        self.client.force_authenticate(user=self.owner)
        
        data = {
            'title': 'Test Parking',
            'description': 'Test Description',
            'address': 'Test Address',
            'city': 'Test City',
            'area': 'Test Area',
            'location': '77.2090,28.6139',
            'space_type': 'garage',
            'total_spaces': 10,
            'available_spaces': 10,
            'price_per_day': 500,
            'accepted_payment_methods': '["razorpay", "cod"]',
            'allowed_vehicle_types': '["car"]',
            'available_from': '06:00',
            'available_until': '23:00',
        }
        
        response = self.client.post('/api/v1/parking-spaces/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_search_nearby_parking(self):
        ParkingSpace.objects.create(
            owner=self.owner,
            title='Nearby Parking',
            description='Test',
            address='Test Address',
            city='Delhi',
            area='Test Area',
            location=Point(77.2090, 28.6139),
            space_type='garage',
            total_spaces=5,
            available_spaces=5,
            price_per_day=500,
            accepted_payment_methods='["razorpay"]',
            allowed_vehicle_types='["car"]',
            available_from='06:00',
            available_until='23:00',
        )
        
        self.client.force_authenticate(user=self.driver)
        response = self.client.get(
            '/api/v1/parking-spaces/nearby/',
            {'lat': 28.6139, 'lng': 77.2090, 'radius': 5}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)


Create file: tests/test_bookings.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.parking.models import ParkingSpace
from apps.bookings.models import Booking
from apps.users.models import DriverVehicle
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta

User = get_user_model()

class BookingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username='owner1',
            email='owner@test.com',
            password='testpass123',
            phone_number='+919876543210',
            user_type='owner'
        )
        
        self.driver = User.objects.create_user(
            username='driver1',
            email='driver@test.com',
            password='testpass123',
            phone_number='+919876543211',
            user_type='driver'
        )
        
        self.parking = ParkingSpace.objects.create(
            owner=self.owner,
            title='Test Parking',
            description='Test',
            address='Test Address',
            city='Delhi',
            area='Test Area',
            location=Point(77.2090, 28.6139),
            space_type='garage',
            total_spaces=5,
            available_spaces=5,
            price_per_day=500,
            accepted_payment_methods='["razorpay"]',
            allowed_vehicle_types='["car"]',
            available_from='06:00',
            available_until='23:00',
        )
        
        self.vehicle = DriverVehicle.objects.create(
            driver=self.driver,
            vehicle_number='DL01AB1234',
            vehicle_type='Car',
            vehicle_model='Honda City',
            dl_number='DL1234567890',
            dl_expiry_date='2025-12-31',
            vehicle_registration_number='DL-01-AB-1234',
            length_in_meters=4.5,
            height_in_meters=1.6,
            width_in_meters=1.8,
        )
    
    def test_driver_can_create_booking(self):
        self.client.force_authenticate(user=self.driver)
        
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(days=1)
        
        data = {
            'parking_space': self.parking.id,
            'vehicle_id': self.vehicle.id,
            'booking_type': 'daily',
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
        }
        
        response = self.client.post('/api/v1/bookings/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending_payment')
    
    def test_overlapping_booking_fails(self):
        start = datetime.now() + timedelta(days=1)
        end = start + timedelta(days=1)
        
        # Create first booking
        Booking.objects.create(
            driver=self.driver,
            parking_space=self.parking,
            vehicle=self.vehicle,
            booking_type='daily',
            start_datetime=start,
            end_datetime=end,
            status='confirmed',
            base_price=500,
            total_price=500,
        )
        
        self.client.force_authenticate(user=self.driver)
        
        # Try to create overlapping booking
        data = {
            'parking_space': self.parking.id,
            'vehicle_id': self.vehicle.id,
            'booking_type': 'daily',
            'start_datetime': start.isoformat(),
            'end_datetime': end.isoformat(),
        }
        
        response = self.client.post('/api/v1/bookings/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
"""


# ==================== IMPORTANT IMPLEMENTATION NOTES ====================
"""
KEY POINTS FOR IMPLEMENTATION:

1. DATABASE SETUP:
   - Use PostgreSQL with PostGIS extension for geolocation queries
   - Enable UUID for all models (recommended for security)
   - Create indices on frequently queried fields (status, city, owner_id)

2. LOCATION TRACKING:
   - Store current location in BookingLocation model
   - Update every 30-60 seconds from Android app
   - Calculate ETA based on distance and average speed (40 km/h)
   - Owner gets real-time updates via WebSocket or polling

3. PAYMENT INTEGRATION:
   - Razorpay webhook for payment notifications
   - Store transaction ID for reconciliation
   - Auto-refund on cancellation (within 24 hours)
   - COD: Owner marks as paid after collection

4. VEHICLE VALIDATION:
   - Check vehicle dimensions against parking space max limits
   - Validate DL expiry date before allowing booking
   - Unique vehicle_number per driver (no duplicates)
   - Allow same DL for multiple vehicles

5. PARKING AVAILABILITY:
   - Real-time update when booking created/cancelled
   - Check availability by querying active bookings
   - Consider time slots and maintenance windows
   - Auto-update status to 'booked' when no spaces available

6. SECURITY:
   - Use JWT with refresh tokens
   - Implement rate limiting on API endpoints
   - Validate all input data (lat/lng ranges, phone formats)
   - Use HTTPS in production
   - Hash sensitive data (DL number, etc)

7. PERFORMANCE:
   - Cache frequently accessed parking spaces
   - Use select_related() and prefetch_related() for queries
   - Implement pagination (20-50 items per page)
   - Use database indices on search fields
   - Consider Redis for real-time data

8. ERROR HANDLING:
   - Return meaningful error messages
   - Log all errors for debugging
   - Implement retry logic for failed payments
   - Handle network timeouts gracefully

9. NOTIFICATIONS:
   - Email notifications for bookings and reviews
   - Push notifications via Firebase Cloud Messaging
   - SMS for payment confirmations
   - In-app notifications for updates

10. TESTING:
    - Write unit tests for all models
    - Integration tests for API endpoints
    - Test with overlapping bookings
    - Test payment scenarios (success, failure, timeout)
    - Load testing for high traffic scenarios

11. DEPLOYMENT:
    - Use Docker/Docker Compose for containerization
    - Use Gunicorn as WSGI server
    - Use Nginx as reverse proxy
    - Enable CORS for mobile app
    - Configure environment variables securely

12. MOBILE APP INTEGRATION:
    - Token refresh before expiry
    - Handle offline scenarios gracefully
    - Cache booking data locally
    - Implement background location tracking
    - Handle app lifecycle events properly
"""