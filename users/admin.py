# ==================== USERS/ADMIN.PY ====================
from django.contrib import admin
from .models import CustomUser, DriverVehicle

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'phone_number', 'user_type', 'is_verified', 'created_at']
    list_filter = ['user_type', 'is_verified', 'created_at']
    search_fields = ['username', 'email', 'phone_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DriverVehicle)
class DriverVehicleAdmin(admin.ModelAdmin):
    list_display = ['vehicle_number', 'driver', 'vehicle_type', 'is_active', 'created_at']
    list_filter = ['vehicle_type', 'is_active']
    search_fields = ['vehicle_number', 'driver__username']
    readonly_fields = ['created_at', 'updated_at']