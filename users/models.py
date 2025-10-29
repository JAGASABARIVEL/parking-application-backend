from django.db import models
from django.contrib.auth.models import AbstractUser
from phonenumber_field.modelfields import PhoneNumberField

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('owner', 'Parking Space Owner'),
        ('driver', 'Regular User'),
        ('both', 'Both'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='driver')
    phone_number = PhoneNumberField(unique=True, blank=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # Ratings
    owner_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    owner_total_reviews = models.IntegerField(default=0)
    driver_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    driver_total_reviews = models.IntegerField(default=0)
    
    is_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class DriverVehicle(models.Model):
    """Store driver's registered vehicles"""
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vehicles')
    vehicle_number = models.CharField(max_length=20, unique=True, db_index=True)
    vehicle_type = models.CharField(max_length=50)  # Car, Bike, etc
    vehicle_model = models.CharField(max_length=100)
    vehicle_color = models.CharField(max_length=50, null=True, blank=True)
    
    dl_number = models.CharField(max_length=50)  # Driving License
    dl_expiry_date = models.DateField()
    vehicle_registration_number = models.CharField(max_length=50)
    
    # Vehicle dimensions for validation against parking space requirements
    length_in_meters = models.FloatField()  # Vehicle length
    height_in_meters = models.FloatField()  # Vehicle height
    width_in_meters = models.FloatField()
    
    vehicle_document = models.FileField(upload_to='vehicle_docs/')  # RC/Registration
    dl_document = models.FileField(upload_to='dl_docs/')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('driver', 'vehicle_number')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.driver.username} - {self.vehicle_number}"