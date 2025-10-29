# ==================== DISPUTES/VIEWS.PY ====================
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as rest_filters
from bookings.models import Booking
from .models import Dispute, DisputeComment
from .serializers import DisputeSerializer, DisputeCommentSerializer
from payments.services import RefundService


class DisputeViewSet(viewsets.ModelViewSet):
    """Manage disputes between users"""
    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, rest_filters.OrderingFilter]
    filterset_fields = ['status', 'dispute_type']
    ordering_fields = ['created_at', 'updated_at']
    
    def get_queryset(self):
        """Only show disputes user is involved in or admin all disputes"""
        if self.request.user.is_staff:
            return Dispute.objects.all()
        return Dispute.objects.filter(
            models.Q(raised_by=self.request.user) |
            models.Q(other_party=self.request.user)
        )
    
    @action(detail=False, methods=['post'])
    def raise_dispute(self, request):
        """Raise a new dispute"""
        booking_id = request.data.get('booking_id')
        
        try:
            booking = Booking.objects.get(id=booking_id)
            
            # Can only raise dispute if involved in booking
            if request.user not in [booking.driver, booking.parking_space.owner]:
                return Response(
                    {'error': 'Only involved parties can raise dispute'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Determine other party
            other_party = booking.parking_space.owner if request.user == booking.driver else booking.driver
            
            dispute = Dispute.objects.create(
                booking=booking,
                raised_by=request.user,
                other_party=other_party,
                dispute_type=request.data.get('dispute_type'),
                title=request.data.get('title'),
                description=request.data.get('description'),
                attachments=request.data.get('attachments', [])
            )
            
            serializer = self.get_serializer(dispute)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add comment to dispute"""
        dispute = self.get_object()
        
        try:
            comment = DisputeComment.objects.create(
                dispute=dispute,
                author=request.user,
                comment=request.data.get('comment'),
                attachments=request.data.get('attachments', []),
                is_internal=request.data.get('is_internal', False) and request.user.is_staff
            )
            
            serializer = DisputeCommentSerializer(comment)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def resolve_dispute(self, request, pk=None):
        """Resolve dispute (admin only)"""
        dispute = self.get_object()
        
        try:
            resolution_type = request.data.get('resolution_type')
            resolution_amount = request.data.get('resolution_amount')
            resolution_notes = request.data.get('resolution_notes', '')
            
            dispute.status = 'resolved'
            dispute.resolution_type = resolution_type
            dispute.resolution_amount = resolution_amount
            dispute.resolution_notes = resolution_notes
            dispute.assigned_to = request.user
            dispute.resolved_at = timezone.now()
            dispute.save()
            
            # Process refund if applicable
            if resolution_type == 'refund_full':
                RefundService.initiate_refund(
                    dispute.booking.payment.id,
                    'dispute_resolved',
                    dispute.booking.total_price,
                    refunded_by=request.user
                )
            elif resolution_type == 'refund_partial':
                RefundService.initiate_refund(
                    dispute.booking.payment.id,
                    'dispute_resolved',
                    resolution_amount,
                    refunded_by=request.user
                )
            
            serializer = self.get_serializer(dispute)
            return Response(serializer.data)
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )