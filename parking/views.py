# ============================= PARKINGSPACE VIEWS - FIXED =============================
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance

from .models import ParkingSpace, ParkingSpaceImage
from .serializers import (
    ParkingSpaceListSerializer,
    ParkingSpaceDetailSerializer,
    ParkingSpaceCreateUpdateSerializer
)
from .filters import ParkingSpaceFilter


class ParkingSpaceViewSet(viewsets.ModelViewSet):
    """Parking space listing, creation, and management"""
    
    queryset = ParkingSpace.objects.all()
    filter_backends = [
        DjangoFilterBackend,  # For custom filters
        filters.SearchFilter,  # For search
        filters.OrderingFilter  # For sorting
    ]
    filterset_class = ParkingSpaceFilter  # Use custom filter
    search_fields = ['title', 'address', 'area', 'landmark', 'description']
    ordering_fields = ['created_at', 'rating', 'price_per_day', 'available_spaces']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ParkingSpaceListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ParkingSpaceCreateUpdateSerializer
        return ParkingSpaceDetailSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'nearby', 'search_by_location']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        serializer.save()
    
    def perform_update(self, serializer):
        if self.request.user != serializer.instance.owner:
            raise permissions.PermissionDenied("You can only edit your own parking spaces")
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Search parking spaces near a location
        Query params: lat, lng, radius (in km), city (optional)
        
        Example: /api/v1/parking-spaces/nearby/?lat=28.6139&lng=77.2090&radius=5
        """
        try:
            latitude = float(request.query_params.get('lat'))
            longitude = float(request.query_params.get('lng'))
            radius = float(request.query_params.get('radius', 5))  # Default 5km
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid latitude, longitude, or radius'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_location = Point(longitude, latitude, srid=4326)
        spaces = ParkingSpace.objects.annotate(
            distance=Distance('location', user_location)
        ).filter(
            distance__lte=radius * 1000,  # Convert km to meters
            status='available'
        ).order_by('distance')
        
        serializer = self.get_serializer(spaces, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search_by_location(self, request):
        """Search parking spaces by city, area, or landmark
        Query params: city, area, landmark, price_min, price_max
        
        Example: /api/v1/parking-spaces/search_by_location/?city=Delhi&price_min=100&price_max=500
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def owner_stats(self, request, pk=None):
        """Get parking space statistics (owner only)
        
        Returns: total_bookings, completed_bookings, active_bookings, cancelled_bookings, 
                 total_revenue, average_rating, available_spaces, occupancy_rate
        """
        space = self.get_object()
        if request.user != space.owner:
            raise permissions.PermissionDenied()
        
        bookings = space.bookings.all()
        confirmed_bookings = bookings.filter(status__in=['confirmed', 'active', 'parked', 'completed'])
        
        return Response({
            'total_bookings': bookings.count(),
            'completed_bookings': bookings.filter(status='completed').count(),
            'active_bookings': bookings.filter(status__in=['active', 'arrived', 'parked']).count(),
            'cancelled_bookings': bookings.filter(status='cancelled').count(),
            'total_revenue': sum([b.total_price for b in confirmed_bookings]),
            'average_rating': space.rating,
            'available_spaces': space.available_spaces,
            'total_spaces': space.total_spaces,
            'occupancy_rate': round(
                (space.total_spaces - space.available_spaces) / space.total_spaces * 100, 2
            ) if space.total_spaces > 0 else 0
        })
    
    @action(detail=False, methods=['get'])
    def my_spaces(self, request):
        """Get all parking spaces owned by current user"""
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        spaces = ParkingSpace.objects.filter(owner=request.user)
        serializer = self.get_serializer(spaces, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update parking space status
        
        Body: { "status": "available|booked|inactive" }
        """
        space = self.get_object()
        if request.user != space.owner:
            raise permissions.PermissionDenied()
        
        new_status = request.data.get('status')
        if new_status not in ['available', 'booked', 'inactive']:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        space.status = new_status
        space.save()
        return Response({'message': f'Status updated to {new_status}'})
    
    @action(detail=True, methods=['get'])
    def availability_slots(self, request, pk=None):
        """Get available time slots for a parking space
        
        Query params: start_date, end_date (ISO format: 2025-10-27)
        
        Example: /api/v1/parking-spaces/1/availability_slots/?start_date=2025-10-27&end_date=2025-10-31
        """
        space = self.get_object()
        from datetime import datetime, timedelta
        
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start_date and end_date required (ISO format)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        except ValueError:
            return Response(
                {'error': 'Invalid date format (use ISO format: 2025-10-27)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all bookings for this space in date range
        bookings = space.bookings.filter(
            status__in=['confirmed', 'active', 'parked'],
            start_datetime__date__gte=start.date(),
            end_datetime__date__lte=end.date()
        ).order_by('start_datetime')
        
        # Build available slots
        available_slots = []
        current_time = start
        
        for booking in bookings:
            if current_time < booking.start_datetime:
                available_slots.append({
                    'start': current_time.isoformat(),
                    'end': booking.start_datetime.isoformat()
                })
            current_time = max(current_time, booking.end_datetime)
        
        if current_time < end:
            available_slots.append({
                'start': current_time.isoformat(),
                'end': end.isoformat()
            })
        
        return Response(available_slots)