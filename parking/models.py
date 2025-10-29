# parking/models.py - FIXED VERSION

from django.db import models
from django.utils import timezone
from users.models import CustomUser
from django.contrib.gis.db import models as gis_models
from django.core.validators import MinValueValidator


class ParkingSpace(models.Model):
    SPACE_TYPE_CHOICES = (
        ('garage', 'Garage'),
        ('open', 'Open Space'),
        ('covered', 'Covered Space'),
        ('private', 'Private Driveway'),
    )
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('inactive', 'Inactive'),
    )

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='owned_parking_spaces')
    
    # Location info
    title = models.CharField(max_length=200)
    description = models.TextField()
    address = models.CharField(max_length=500)
    location = gis_models.PointField()  # Latitude & Longitude
    city = models.CharField(max_length=100, db_index=True)
    area = models.CharField(max_length=100)
    landmark = models.CharField(max_length=200, null=True, blank=True)
    
    # Space details
    space_type = models.CharField(max_length=20, choices=SPACE_TYPE_CHOICES)
    total_spaces = models.IntegerField(validators=[MinValueValidator(1)])
    available_spaces = models.IntegerField(validators=[MinValueValidator(0)])
    
    # Pricing (flexible pricing model)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_week = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_per_year = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Vehicle restrictions
    max_vehicle_height = models.FloatField(null=True, blank=True)  # In meters
    max_vehicle_length = models.FloatField(null=True, blank=True)  # In meters
    max_vehicle_width = models.FloatField(null=True, blank=True)
    allowed_vehicle_types = models.CharField(max_length=200)  # JSON: ["car", "bike"]
    
    # Amenities
    has_security_camera = models.BooleanField(default=False)
    has_lighting = models.BooleanField(default=False)
    has_ev_charging = models.BooleanField(default=False)
    has_surveillance = models.BooleanField(default=False)
    has_covered = models.BooleanField(default=False)
    has_24_7_access = models.BooleanField(default=False)
    
    # Availability
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', db_index=True)
    available_from = models.TimeField()
    available_until = models.TimeField()
    
    # Payment settings
    accepted_payment_methods = models.CharField(max_length=100)  # JSON: ["cod", "razorpay"]
    
    # Media
    image = models.ImageField(upload_to='parking_spaces/')
    additional_images = models.JSONField(default=list)  # List of image URLs
    
    # Stats
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_bookings = models.IntegerField(default=0)
    total_reviews = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        # FIXED: Removed GistIndex which is not available
        # The location field will still be queryable by GIS queries
        # If you need better performance on location queries, use database-level GiST index instead
        indexes = [
            models.Index(fields=['city']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.address}"
    
    def is_currently_available(self):
        """Check if space is open now based on available_from and available_until"""
        now = timezone.now().time()
        return self.available_from <= now <= self.available_until


class ParkingSpaceImage(models.Model):
    """Additional images for parking space"""
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='parking_space_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Image for {self.parking_space.title}"


# ===== ALTERNATIVE: If you want to use GiST index at database level =====
# Use this migration instead:
"""
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('parking', '0001_initial'),  # or whatever your last migration is
    ]

    operations = [
        migrations.RunSQL(
            "CREATE INDEX parking_location_gist ON parking_parkingspace USING gist(location);",
            "DROP INDEX parking_location_gist;"
        ),
    ]
"""

# To use this alternative:
# 1. Create a new migration file in parking/migrations/
# 2. Paste the code above
# 3. Run: python manage.py migrate

# ===== SOLUTION SUMMARY =====
"""
PROBLEM: 
    gis_models.GistIndex is not available in Django's ORM models

SOLUTIONS PROVIDED:

1. OPTION A (Recommended - Easy):
   - Remove GistIndex from Meta class (already done above)
   - Django will still allow spatial queries on the location field
   - Performance will be acceptable for most use cases
   - No database-level tweaking needed

2. OPTION B (Better Performance):
   - Use a Django migration to create GiST index directly in PostgreSQL
   - This gives you spatial index performance without ORM
   - Use the migration code provided in comments above

3. OPTION C (If you still want to use GistIndex):
   - Update Django to version 3.2+ which has better GIS support
   - Or import from the correct module:
     from django.contrib.postgres.indexes import GistIndex
     (Note: This is for PostgreSQL-specific features)

NEXT STEPS:
1. Delete any failed migration files
2. Use the fixed models.py above
3. Run: python manage.py makemigrations
4. Run: python manage.py migrate
5. If you want GiST index, use OPTION B above
"""