# ==================== PARKING/SERIALIZERS.PY ====================
from rest_framework import serializers
from .models import ParkingSpace, ParkingSpaceImage
from django.contrib.gis.geos import Point
from users.serializers import UserProfileSerializer

class ParkingSpaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParkingSpaceImage
        fields = ['id', 'image', 'uploaded_at']


class ParkingSpaceListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing parking spaces"""
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    distance = serializers.SerializerMethodField()
    images = ParkingSpaceImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ParkingSpace
        fields = ['id', 'title', 'address', 'area', 'space_type', 'available_spaces', 'total_spaces',
                  'price_per_day', 'price_per_week', 'price_per_month', 'price_per_year', 'rating', 
                  'image', 'images', 'has_security_camera', 'has_lighting', 'has_ev_charging', 
                  'owner_name', 'location', 'distance', 'landmark', 'total_bookings']
    
    def get_distance(self, obj):
        """Calculate distance from request location if provided"""
        request = self.context.get('request')
        if request and 'lat' in request.query_params and 'lng' in request.query_params:
            from geopy.distance import geodesic
            try:
                user_location = (float(request.query_params['lat']), float(request.query_params['lng']))
                space_location = (obj.location.y, obj.location.x)
                distance = geodesic(user_location, space_location).km
                return round(distance, 2)
            except:
                return None
        return None



class ParkingSpaceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for parking space with all info"""
    owner = UserProfileSerializer(read_only=True)
    images = ParkingSpaceImageSerializer(many=True, read_only=True)
    allowed_vehicle_types = serializers.JSONField()
    accepted_payment_methods = serializers.JSONField()
    
    class Meta:
        model = ParkingSpace
        fields = '__all__'
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['owner'] = user
        return super().create(validated_data)


class ParkingSpaceCreateUpdateSerializer(serializers.ModelSerializer):
    """For creating/updating parking spaces"""
    images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = ParkingSpace
        fields = ['title', 'description', 'address', 'city', 'area', 'landmark', 'location',
                  'space_type', 'total_spaces', 'available_spaces', 'price_per_day', 'price_per_week',
                  'price_per_month', 'price_per_year', 'max_vehicle_height', 'max_vehicle_length',
                  'max_vehicle_width', 'allowed_vehicle_types', 'has_security_camera', 'has_lighting',
                  'has_ev_charging', 'has_surveillance', 'has_covered', 'has_24_7_access',
                  'available_from', 'available_until', 'accepted_payment_methods', 'image', 'images']
    
    def create(self, validated_data):
        images = validated_data.pop('images', [])
        print("self.context['request'].user ", self.context['request'].user)
        space = ParkingSpace.objects.create(owner=self.context['request'].user, **validated_data)
        
        for image in images:
            ParkingSpaceImage.objects.create(parking_space=space, image=image)
        
        return space












