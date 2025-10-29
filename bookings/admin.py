
# ==================== BOOKINGS/ADMIN.PY ====================
from django.contrib import admin
from .models import Booking, BookingLocation, Review

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['id', 'driver', 'parking_space', 'status', 'booking_type', 'start_datetime', 'total_price', 'created_at']
    list_filter = ['status', 'booking_type', 'created_at']
    search_fields = ['driver__username', 'parking_space__title', 'vehicle__vehicle_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['reviewer', 'reviewed_user', 'rating', 'booking', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['reviewer__username', 'reviewed_user__username']
    readonly_fields = ['created_at', 'updated_at']