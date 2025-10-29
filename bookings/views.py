# ============================= BOOKINGS VIEWS - FIXED =============================
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from bookings.models import Booking, BookingLocation, Review
from bookings.serializers import (
    BookingCreateSerializer,
    BookingListSerializer,
    BookingDetailSerializer,
    BookingLocationUpdateSerializer,
    ReviewSerializer
)


class BookingViewSet(viewsets.ModelViewSet):
    """Booking creation, management, and tracking"""
    
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,  # For filtering
        filters.SearchFilter,  # For searching
        filters.OrderingFilter  # For ordering
    ]
    filterset_fields = ['status', 'booking_type']  # Fields you can filter by
    search_fields = ['parking_space__title', 'parking_space__address', 'vehicle__vehicle_number']
    ordering_fields = ['created_at', 'start_datetime', 'total_price']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action == 'list':
            return BookingListSerializer
        return BookingDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        # Drivers see their own bookings
        if user.user_type in ['driver', 'both']:
            return Booking.objects.filter(driver=user)
        # Owners see bookings for their spaces
        elif user.user_type == 'owner':
            return Booking.objects.filter(parking_space__owner=user)
        return Booking.objects.none()
    
    @action(detail=False, methods=['get'])
    def my_bookings(self, request):
        """Get all bookings for current user (driver)"""
        if request.user.user_type not in ['driver', 'both']:
            return Response(
                {'error': 'Only drivers can view their bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        bookings = Booking.objects.filter(driver=request.user)
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_space_bookings(self, request):
        """Get all bookings for owner's parking spaces"""
        if request.user.user_type not in ['owner', 'both']:
            return Response(
                {'error': 'Only owners can view space bookings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        bookings = Booking.objects.filter(
            parking_space__owner=request.user
        ).order_by('-start_datetime')
        serializer = self.get_serializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update booking status
        
        Body: { "status": "confirmed|active|arrived|parked|completed|cancelled" }
        """
        booking = self.get_object()
        
        # Check permissions
        if request.user != booking.driver and request.user != booking.parking_space.owner:
            raise permissions.PermissionDenied()
        
        new_status = request.data.get('status')
        valid_statuses = ['pending_payment', 'confirmed', 'active', 'arrived', 'parked', 'completed', 'cancelled']
        
        if new_status not in valid_statuses:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = new_status
        booking.save()
        
        # Update parking space availability
        if new_status == 'cancelled':
            booking.parking_space.available_spaces += 1
            booking.parking_space.save()
        
        return Response(BookingDetailSerializer(booking).data)
    
    @action(detail=True, methods=['post'])
    def cancel_booking(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        if request.user != booking.driver:
            raise permissions.PermissionDenied()
        
        if booking.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel a {booking.status} booking'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save()
        booking.parking_space.available_spaces += 1
        booking.parking_space.save()
        
        return Response({'message': 'Booking cancelled successfully'})
    
    @action(detail=True, methods=['put'])
    def update_location(self, request, pk=None):
        """Update driver's current location (real-time tracking)"""
        booking = self.get_object()
        
        if request.user != booking.driver:
            raise permissions.PermissionDenied()
        
        if booking.status not in ['active', 'arrived']:
            return Response(
                {'error': 'Booking is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location_tracking = booking.location_tracking
            serializer = BookingLocationUpdateSerializer(
                location_tracking,
                data=request.data,
                partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except BookingLocation.DoesNotExist:
            return Response(
                {'error': 'Location tracking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def tracking_info(self, request, pk=None):
        """Get real-time tracking info for a booking"""
        booking = self.get_object()
        
        if request.user != booking.parking_space.owner and request.user != booking.driver:
            raise permissions.PermissionDenied()
        
        try:
            tracking = booking.location_tracking
            return Response({
                'booking_id': booking.id,
                'driver_name': booking.driver.get_full_name(),
                'vehicle_number': booking.vehicle.vehicle_number,
                'current_location': {
                    'latitude': tracking.current_latitude,
                    'longitude': tracking.current_longitude,
                },
                'destination': {
                    'latitude': tracking.destination_latitude,
                    'longitude': tracking.destination_longitude,
                },
                'distance_remaining': tracking.distance_remaining,
                'eta_minutes': tracking.eta_minutes,
                'reached_destination': tracking.reached_destination,
                'is_tracking_active': tracking.is_tracking_active
            })
        except BookingLocation.DoesNotExist:
            return Response(
                {'error': 'Tracking info not available'},
                status=status.HTTP_404_NOT_FOUND
            )


class ReviewViewSet(viewsets.ModelViewSet):
    """Create and manage reviews"""
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_review(self, request):
        """Create a review for a completed booking"""
        booking_id = request.data.get('booking_id')
        rating = request.data.get('rating')
        comment = request.data.get('comment', '')
        tags = request.data.get('tags', [])
        
        try:
            booking = Booking.objects.get(id=booking_id, status='completed')
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found or not completed'}, 
                          status=status.HTTP_404_NOT_FOUND)
        
        # Determine who is reviewing whom
        if request.user == booking.driver:
            reviewed_user = booking.parking_space.owner
        elif request.user == booking.parking_space.owner:
            reviewed_user = booking.driver
        else:
            raise permissions.PermissionDenied()
        
        review, created = Review.objects.get_or_create(
            booking=booking,
            reviewer=request.user,
            defaults={'reviewed_user': reviewed_user, 'rating': rating, 'comment': comment, 'tags': tags}
        )
        
        if not created:
            return Response({'error': 'Review already exists for this booking'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        # Update user ratings
        user_reviews = Review.objects.filter(reviewed_user=reviewed_user)
        avg_rating = sum([r.rating for r in user_reviews]) / user_reviews.count()
        
        if reviewed_user.user_type in ['owner', 'both']:
            reviewed_user.owner_rating = avg_rating
            reviewed_user.owner_total_reviews = user_reviews.count()
        else:
            reviewed_user.driver_rating = avg_rating
            reviewed_user.driver_total_reviews = user_reviews.count()
        
        reviewed_user.save()
        
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)