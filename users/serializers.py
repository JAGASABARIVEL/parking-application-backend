# ==================== USERS/SERIALIZERS.PY ====================
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import CustomUser, DriverVehicle

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'user_type', 'password', 'password_confirm']
    
    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords do not match"})
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = CustomUser.objects.create_user(password=password, **validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        data['user'] = user
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    owner_rating = serializers.ReadOnlyField()
    driver_rating = serializers.ReadOnlyField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number', 'user_type', 
                  'profile_picture', 'bio', 'owner_rating', 'owner_total_reviews', 'driver_rating', 
                  'driver_total_reviews', 'is_verified', 'phone_verified', 'email_verified']
        read_only_fields = ['is_verified', 'owner_rating', 'driver_rating']


class DriverVehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverVehicle
        fields = ['id', 'vehicle_number', 'vehicle_type', 'vehicle_model', 'vehicle_color', 
                  'dl_number', 'dl_expiry_date', 'length_in_meters', 'height_in_meters', 'width_in_meters',
                  'vehicle_document', 'dl_document', 'is_active', 'created_at']
        read_only_fields = ['created_at']
    
    def validate_vehicle_number(self, value):
        # Check if vehicle already registered by another driver
        if DriverVehicle.objects.filter(vehicle_number=value).exclude(driver=self.context['request'].user).exists():
            raise serializers.ValidationError("This vehicle number is already registered by another driver")
        return value.upper()


