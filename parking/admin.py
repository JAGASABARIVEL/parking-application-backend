# ==================== PARKING/ADMIN.PY ====================
from django.contrib import admin
from .models import ParkingSpace, ParkingSpaceImage

class ParkingSpaceImageInline(admin.TabularInline):
    model = ParkingSpaceImage
    extra = 1

@admin.register(ParkingSpace)
class ParkingSpaceAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'city', 'space_type', 'status', 'available_spaces', 'rating', 'created_at']
    list_filter = ['space_type', 'status', 'city', 'created_at']
    search_fields = ['title', 'address', 'owner__username']
    readonly_fields = ['created_at', 'updated_at', 'total_bookings', 'rating']
    inlines = [ParkingSpaceImageInline]
    fieldsets = (
        ('Basic Info', {'fields': ('owner', 'title', 'description', 'address', 'city', 'area')}),
        ('Location', {'fields': ('location', 'landmark')}),
        ('Space Details', {'fields': ('space_type', 'total_spaces', 'available_spaces', 'status')}),
        ('Pricing', {'fields': ('price_per_day', 'price_per_week', 'price_per_month', 'price_per_year')}),
        ('Vehicle Restrictions', {'fields': ('max_vehicle_height', 'max_vehicle_length', 'max_vehicle_width', 'allowed_vehicle_types')}),
        ('Amenities', {'fields': ('has_security_camera', 'has_lighting', 'has_ev_charging', 'has_surveillance', 'has_covered', 'has_24_7_access')}),
        ('Availability', {'fields': ('available_from', 'available_until')}),
        ('Payment & Stats', {'fields': ('accepted_payment_methods', 'rating', 'total_bookings')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )