# ==================== BOOKINGS/TASKS.PY (CELERY TASKS) ====================
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from .models import Booking, BookingLocation
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task
def auto_complete_bookings():
    """Automatically complete bookings that have ended"""
    now = timezone.now()
    ended_bookings = Booking.objects.filter(
        end_datetime__lte=now,
        status__in=['active', 'arrived', 'parked']
    )
    
    for booking in ended_bookings:
        booking.status = 'completed'
        booking.save()
        
        # Send notification to driver and owner
        send_booking_completion_notification(booking)
    
    logger.info(f"Auto-completed {ended_bookings.count()} bookings")


@shared_task
def check_abandoned_bookings():
    """Check for bookings where driver hasn't arrived within expected time"""
    now = timezone.now()
    abandoned_threshold = now - timedelta(hours=1)
    
    active_bookings = Booking.objects.filter(
        status='active',
        start_datetime__lte=abandoned_threshold
    )
    
    for booking in active_bookings:
        tracking = booking.location_tracking
        if not tracking.reached_destination:
            notify_owner_delayed_arrival(booking)


@shared_task
def send_booking_notification(booking_id):
    """Send booking confirmation notification"""
    try:
        booking = Booking.objects.get(id=booking_id)
        owner = booking.parking_space.owner
        driver = booking.driver
        
        # Send email to owner
        send_mail(
            f'New Booking for {booking.parking_space.title}',
            f'''
            A new booking has been confirmed:
            Driver: {driver.get_full_name()}
            Vehicle: {booking.vehicle.vehicle_number}
            Check-in: {booking.start_datetime}
            Check-out: {booking.end_datetime}
            Amount: {booking.total_price}
            ''',
            'noreply@parkingapp.com',
            [owner.email],
            fail_silently=False,
        )
        
        # Send email to driver
        send_mail(
            f'Booking Confirmed - {booking.parking_space.title}',
            f'''
            Your booking has been confirmed:
            Location: {booking.parking_space.address}
            Check-in: {booking.start_datetime}
            Check-out: {booking.end_datetime}
            Amount: {booking.total_price}
            Contact: {owner.phone_number}
            ''',
            'noreply@parkingapp.com',
            [driver.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Error sending booking notification: {str(e)}")


def send_booking_completion_notification(booking):
    """Send notification when booking is completed"""
    owner = booking.parking_space.owner
    driver = booking.driver
    
    # Notify to submit review
    send_mail(
        'Your booking has been completed',
        f'Please review your recent parking experience at {booking.parking_space.title}',
        'noreply@parkingapp.com',
        [driver.email],
        fail_silently=True,
    )


def notify_owner_delayed_arrival(booking):
    """Notify owner that driver is delayed"""
    owner = booking.parking_space.owner
    
    send_mail(
        'Driver Delayed Arrival - Booking Alert',
        f'Driver {booking.driver.get_full_name()} for booking {booking.id} has not arrived yet.',
        'noreply@parkingapp.com',
        [owner.email],
        fail_silently=True,
    )


