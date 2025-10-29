# ==================== BOOKINGS/SERIALIZERS.PY ====================
from rest_framework import serializers
from .models import Booking, BookingLocation, Review
from parking.serializers import ParkingSpaceListSerializer
from users.models import DriverVehicle
from users.serializers import DriverVehicleSerializer

class BookingCreateSerializer(serializers.ModelSerializer):
    vehicle_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'parking_space', 'vehicle_id', 'booking_type', 'start_datetime', 'end_datetime',
                  'special_instructions']
        read_only_fields = ['id']  # ✅ ensures it's returned, not expected in POST

    def validate(self, data):
        parking_space = data['parking_space']
        start_datetime = data['start_datetime']
        end_datetime = data['end_datetime']
        
        # Validate booking doesn't overlap with existing confirmed bookings
        overlapping = Booking.objects.filter(
            parking_space=parking_space,
            status__in=['confirmed', 'active', 'arrived', 'parked'],
            start_datetime__lt=end_datetime,
            end_datetime__gt=start_datetime
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError("Parking space not available for selected time")
        
        # CHECK: Owner must not be blocked
        from payments.services import CommissionService
        if not CommissionService.can_owner_receive_payment(parking_space.owner):
            return Response(
                {'error': 'Parking space owner account is currently blocked. Please try another space.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate end time is after start time
        if end_datetime <= start_datetime:
            raise serializers.ValidationError("End time must be after start time")
        
        return data
    
    def create(self, validated_data):
        vehicle_id = validated_data.pop('vehicle_id')
        user = self.context['request'].user
        vehicle = DriverVehicle.objects.get(id=vehicle_id, driver=user)
        
        booking = Booking(
            driver=user,
            vehicle=vehicle,
            **validated_data
        )
        
        booking.calculate_price()
        booking.save()
        
        # Create location tracking
        BookingLocation.objects.create(
            booking=booking,
            destination_latitude=booking.parking_space.location.y,
            destination_longitude=booking.parking_space.location.x
        )
        
        return booking


class BookingListSerializer(serializers.ModelSerializer):
    parking_space_title = serializers.CharField(source='parking_space.title', read_only=True)
    vehicle_number = serializers.CharField(source='vehicle.vehicle_number', read_only=True)
    owner_name = serializers.CharField(source='parking_space.owner.get_full_name', read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'parking_space', 'parking_space_title', 'vehicle_number', 'booking_type',
                  'start_datetime', 'end_datetime', 'status', 'total_price', 'owner_name', 'created_at']
        read_only_fields = ['created_at']


class BookingDetailSerializer(serializers.ModelSerializer):
    parking_space = ParkingSpaceListSerializer(read_only=True)
    vehicle = DriverVehicleSerializer(read_only=True)
    location_tracking = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    payment_breakdown = serializers.SerializerMethodField()
    
    
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['driver', 'created_at', 'updated_at', 'payment_breakdown']
    
    def get_payment_breakdown(self, obj):
        return obj.get_payment_breakdown()

    def get_location_tracking(self, obj):
        try:
            tracking = obj.location_tracking
            return {
                'current_latitude': tracking.current_latitude,
                'current_longitude': tracking.current_longitude,
                'destination_latitude': tracking.destination_latitude,
                'destination_longitude': tracking.destination_longitude,
                'distance_remaining': tracking.distance_remaining,
                'eta_minutes': tracking.eta_minutes,
                'reached_destination': tracking.reached_destination,
                'is_tracking_active': tracking.is_tracking_active
            }
        except:
            return None
    
    def get_review(self, obj):
        try:
            review = obj.review
            return ReviewSerializer(review).data
        except:
            return None


class BookingLocationUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingLocation
        fields = ['current_latitude', 'current_longitude', 'distance_remaining', 'eta_minutes']


class ReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    reviewed_user_name = serializers.CharField(source='reviewed_user.get_full_name', read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'booking', 'reviewer_name', 'reviewed_user_name', 'rating', 'comment', 'tags', 'created_at']
        read_only_fields = ['reviewer', 'reviewed_user', 'created_at']