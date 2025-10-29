# ==================== PARKING/SIGNALS.PY (Django Signals) ====================
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import ParkingSpace, Booking
from bookings.models import Booking as BookingModel
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=BookingModel)
def booking_status_changed(sender, instance, created, **kwargs):
    """Signal handler for booking status changes"""
    if created:
        # New booking created
        logger.info(f"New booking created: {instance.id}")
    else:
        # Booking updated
        if instance.status == 'confirmed':
            # Reduce available spaces
            instance.parking_space.available_spaces = max(0, instance.parking_space.available_spaces - 1)
            instance.parking_space.save()
        
        elif instance.status == 'cancelled':
            # Increase available spaces
            instance.parking_space.available_spaces += 1
            instance.parking_space.save()
        
        elif instance.status == 'completed':
            # Increment total bookings
            instance.parking_space.total_bookings += 1
            instance.parking_space.save()


@receiver(post_save, sender=ParkingSpace)
def update_space_status(sender, instance, **kwargs):
    """Auto-update parking space status based on availability"""
    if instance.available_spaces <= 0:
        instance.status = 'booked'
    else:
        instance.status = 'available'
    instance.save()