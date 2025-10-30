from decimal import Decimal
from django.db import models
from django.utils import timezone
from users.models import CustomUser, DriverVehicle
from parking.models import ParkingSpace


class Booking(models.Model):
    STATUS_CHOICES = (
        ('pending_payment', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('active', 'Active - Driver En Route'),
        ('arrived', 'Arrived at Location'),
        ('parked', 'Vehicle Parked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    BOOKING_TYPE_CHOICES = (
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )

    # Relations
    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='driver_bookings')
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.CASCADE, related_name='bookings')
    vehicle = models.ForeignKey(DriverVehicle, on_delete=models.SET_NULL, null=True)
    
    # Booking details
    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPE_CHOICES)
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending_payment', db_index=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Special notes
    special_instructions = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['parking_space', 'status']),
        ]
    
    def __str__(self):
        return f"Booking {self.id} - {self.driver.username} at {self.parking_space.title}"
    
    def calculate_price(self):
        """Calculate price based on booking type and duration"""
        from datetime import timedelta
        
        duration = self.end_datetime - self.start_datetime
        
        if self.booking_type == 'hourly':
            hours = duration.total_seconds() / 3600
            # Calculate hourly rate from daily price
            daily_price = self.parking_space.price_per_day or 0
            self.base_price = (daily_price / 24) * hours
        elif self.booking_type == 'daily':
            days = duration.days or 1
            print("days ", days)
            print("self.parking_space.price_per_day ", self.parking_space.price_per_day)
            self.base_price = (self.parking_space.price_per_day or 0) * days
        elif self.booking_type == 'weekly':
            weeks = duration.days // 7 or 1
            self.base_price = (self.parking_space.price_per_week or 0) * weeks
        elif self.booking_type == 'monthly':
            months = (duration.days // 30) or 1
            self.base_price = (self.parking_space.price_per_month or 0) * months
        elif self.booking_type == 'yearly':
            self.base_price = self.parking_space.price_per_year or 0
        
        self.total_price = self.base_price - self.discount
        return self.total_price
    
    def get_payment_breakdown(self):
        '''Get detailed payment breakdown'''
        from payments.models import CommissionTransaction
        from payments.services import CommissionService
        
        settings = CommissionService.get_settings()
        
        # Calculate commission
        commission = (Decimal(self.total_price) * Decimal(settings.commission_percentage)) / Decimal(100)
        commission = max(commission, Decimal(settings.minimum_commission))
        
        processing_fee = (Decimal(self.total_price) * Decimal(settings.payment_processing_fee)) / Decimal(100)
        
        owner_gets = self.total_price - commission - processing_fee
        
        return {
            'booking_amount': self.total_price,
            'commission': commission,
            'commission_percentage': settings.commission_percentage,
            'processing_fee': processing_fee,
            'owner_receives': owner_gets,
        }

class BookingLocation(models.Model):
    """Real-time location tracking for active bookings"""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='location_tracking')
    # Current location
    current_latitude = models.FloatField(null=True)
    current_longitude = models.FloatField(null=True)
    
    # Destination
    destination_latitude = models.FloatField()
    destination_longitude = models.FloatField()
    
    # Distance info
    distance_remaining = models.FloatField(null=True)  # In kilometers
    eta_minutes = models.IntegerField(null=True)  # Estimated Time of Arrival
    
    # Status
    is_tracking_active = models.BooleanField(default=True)
    reached_destination = models.BooleanField(default=False)
    reached_at = models.DateTimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Location Tracking for Booking {self.booking.id}"

class Review(models.Model):
    """Reviews for parking spaces and drivers"""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    # Who reviews whom
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='given_reviews')
    reviewed_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_reviews')
    
    # Review content
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    
    # Tags for categorization
    tags = models.JSONField(default=list)  # ["clean", "safe", "convenient"]
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('booking', 'reviewer')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Review by {self.reviewer.username} for {self.reviewed_user.username}"


class BookingPayout(models.Model):
    """Track payout details for each booking"""
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='payout'
    )
    
    # Amounts
    booking_amount = models.DecimalField(max_digits=15, decimal_places=2)
    commission_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processing_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    owner_payout_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Status
    payout_status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('due_from_cod', 'Due from COD'),
            ('settled', 'Settled'),
            ('failed', 'Failed'),
        ]
    )
    payment_method_used = models.CharField(max_length=20)  # razorpay, cod
    
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout for Booking {self.booking.id} - ₹{self.owner_payout_amount}"
