# ==================== PAYMENTS/VIEWS.PY ====================
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import datetime, timedelta
import logging
from django.conf import settings
from decimal import Decimal
from django.db import transaction

from bookings.models import Booking
from .models import (
    Payment, Refund, CommissionSettings, OwnerCommissionAccount,
    CommissionTransaction, CommissionDue, PayoutRequest
)
from .serializers import (
    PaymentSerializer, PaymentInitiateSerializer, PaymentVerifySerializer,
    RefundSerializer, RefundInitiateSerializer,
    CommissionSettingsSerializer, OwnerCommissionAccountSerializer,
    CommissionTransactionSerializer, CommissionDueSerializer,
    PayoutRequestSerializer
)
from .services import RazorpayService, CommissionService, RefundService, PayoutService

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ViewSet):
    """Handle payment processing, verification, and status"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def initiate_payment(self, request):
        """Initiate payment for a booking
        
        Body: {
            "booking_id": 1,
            "payment_method": "razorpay|cod"
        }
        """
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking = Booking.objects.get(id=serializer.validated_data['booking_id'])
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.user != booking.driver:
            return Response(
                {'error': 'Only booking driver can initiate payment'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if booking.status != 'pending_payment':
            return Response(
                {'error': f'Cannot pay for booking in {booking.status} status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = serializer.validated_data['payment_method']
        
        # Get or create payment
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'amount': booking.total_price,
                'payment_method': payment_method,
                'status': 'initiated'
            }
        )
        
        if not created and payment.status != 'initiated':
            return Response(
                {'error': f'Payment already {payment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if payment_method == 'razorpay':
                razorpay_service = RazorpayService()
                razorpay_order = razorpay_service.create_order(
                    booking.id,
                    booking.total_price
                )
                
                payment.razorpay_order_id = razorpay_order['id']
                payment.status = 'initiated'
                payment.save()
                
                return Response({
                    'payment_id': payment.id,
                    'razorpay_order_id': razorpay_order['id'],
                    'amount': float(booking.total_price),
                    'currency': 'INR',
                    'key_id': settings.RAZORPAY_KEY_ID
                }, status=status.HTTP_200_OK)
            
            elif payment_method == 'cod':
                payment.status = 'initiated'
                payment.save()

                # Process payment
                booking = payment.booking
                CommissionService.process_cod_payment(
                    booking,
                    payment
                )
                
                # Update booking status
                booking.status = 'confirmed'
                booking.parking_space.available_spaces -= 1
                booking.save()
                booking.parking_space.save()
                
                return Response({
                    'payment_id': payment.id,
                    'message': 'COD selected. Confirm booking to proceed',
                    'payment_method': 'cod'
                }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Payment initiation error: {str(e)}")
            return Response(
                {'error': 'Failed to initiate payment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verify_payment(self, request):
        """Verify Razorpay payment
        
        Body: {
            "razorpay_order_id": "order_xxx",
            "razorpay_payment_id": "pay_xxx",
            "razorpay_signature": "sig_xxx"
        }
        """
        serializer = PaymentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payment = Payment.objects.get(
                razorpay_order_id=serializer.validated_data['razorpay_order_id']
            )
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Verify payment signature
            razorpay_service = RazorpayService()
            is_valid = razorpay_service.verify_payment(
                serializer.validated_data['razorpay_order_id'],
                serializer.validated_data['razorpay_payment_id'],
                serializer.validated_data['razorpay_signature']
            )
            
            if not is_valid:
                payment.status = 'failed'
                payment.save()
                return Response(
                    {'error': 'Payment verification failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process payment
            booking = payment.booking
            CommissionService.process_razorpay_payment(
                booking,
                payment,
                serializer.validated_data['razorpay_payment_id']
            )
            
            # Update booking status
            booking.status = 'confirmed'
            booking.parking_space.available_spaces -= 1
            booking.save()
            booking.parking_space.save()
            
            return Response({
                'message': 'Payment verified successfully',
                'booking_id': booking.id,
                'status': booking.status
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return Response(
                {'error': 'Payment processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def confirm_cod_payment(self, request):
        """Confirm COD payment (driver confirms, money due on collection)"""
        booking_id = request.data.get('booking_id')
        
        try:
            booking = Booking.objects.get(id=booking_id)
            
            if request.user != booking.driver:
                return Response(
                    {'error': 'Only booking driver can confirm'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            payment = Payment.objects.get(booking=booking)
            
            # Process COD
            CommissionService.process_cod_payment(booking, payment)
            
            # Update booking
            booking.status = 'confirmed'
            booking.parking_space.available_spaces -= 1
            booking.save()
            booking.parking_space.save()
            
            return Response({
                'message': 'COD booking confirmed',
                'booking_id': booking.id,
                'status': booking.status
            }, status=status.HTTP_200_OK)
        
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"COD confirmation error: {str(e)}")
            return Response(
                {'error': 'Failed to confirm payment'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def payment_status(self, request):
        """Get payment status for a booking"""
        booking_id = request.query_params.get('booking_id')
        
        try:
            payment = Payment.objects.get(booking_id=booking_id)
            serializer = PaymentSerializer(payment)
            return Response(serializer.data)
        except Payment.DoesNotExist:
            return Response(
                {'error': 'Payment not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class RefundViewSet(viewsets.ViewSet):
    """Manage refunds"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def initiate_refund(self, request):
        """Initiate refund for a booking
        
        Body: {
            "booking_id": 1,
            "reason": "booking_cancelled",
            "amount": 500  # optional, full amount if not specified
        }
        """
        booking_id = request.data.get('booking_id')
        reason = request.data.get('reason')
        amount = request.data.get('amount')
        
        try:
            booking = Booking.objects.get(id=booking_id)
            payment = booking.payment
            
            # Only driver or admin can request refund
            if request.user != booking.driver and not request.user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            refund = RefundService.initiate_refund(
                payment.id,
                reason,
                amount,
                refunded_by=request.user if request.user.is_staff else None
            )
            
            serializer = RefundSerializer(refund)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            logger.error(f"Refund initiation error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def refund_status(self, request):
        """Get refund status"""
        booking_id = request.query_params.get('booking_id')
        
        try:
            booking = Booking.objects.get(id=booking_id)
            refund = booking.payment.refund
            serializer = RefundSerializer(refund)
            return Response(serializer.data)
        except:
            return Response(
                {'error': 'No refund found for this booking'},
                status=status.HTTP_404_NOT_FOUND
            )


# ==================== ADMIN COMMISSION VIEWS ====================

class CommissionSettingsViewSet(viewsets.ModelViewSet):
    """Admin - Manage global commission settings"""
    queryset = CommissionSettings.objects.all()
    serializer_class = CommissionSettingsSerializer
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def current_settings(self, request):
        """Get current active settings"""
        settings = CommissionSettings.objects.first()
        if not settings:
            settings = CommissionSettings.objects.create()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=True, methods=['put'])
    def update_settings(self, request, pk=None):
        """Update settings"""
        settings = self.get_object()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OwnerCommissionAccountViewSet(viewsets.ModelViewSet):
    """Admin - View and manage owner commission accounts"""
    queryset = OwnerCommissionAccount.objects.all()
    serializer_class = OwnerCommissionAccountSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['owner__username', 'owner__email']
    ordering_fields = ['pending_dues', 'current_balance', 'total_earned']
    filterset_fields = ['is_blocked', 'account_status']
    
    @action(detail=False, methods=['get'])
    def owners_with_dues(self, request):
        """Get owners with pending dues"""
        accounts = OwnerCommissionAccount.objects.filter(
            pending_dues__gt=0
        ).order_by('-pending_dues')
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def blocked_owners(self, request):
        """Get blocked owners"""
        accounts = OwnerCommissionAccount.objects.filter(is_blocked=True)
        serializer = self.get_serializer(accounts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def block_owner(self, request, pk=None):
        """Block an owner"""
        account = self.get_object()
        reason = request.data.get('reason', 'Admin action')
        
        account.is_blocked = True
        account.account_status = 'blocked'
        account.blocked_reason = reason
        account.blocked_at = timezone.now()
        account.save()
        
        logger.warning(f"Owner {account.owner.username} blocked by admin. Reason: {reason}")
        return Response(self.get_serializer(account).data)
    
    @action(detail=True, methods=['post'])
    def unblock_owner(self, request, pk=None):
        """Unblock an owner"""
        account = self.get_object()
        reason = request.data.get('reason', 'Admin action')
        
        account.unblock(reason)
        return Response(self.get_serializer(account).data)
    
    @action(detail=True, methods=['get'])
    def commission_history(self, request, pk=None):
        """Get commission history"""
        account = self.get_object()
        transactions = CommissionTransaction.objects.filter(
            owner=account.owner
        ).order_by('-created_at')
        serializer = CommissionTransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def pending_dues(self, request, pk=None):
        """Get pending dues"""
        account = self.get_object()
        dues = CommissionDue.objects.filter(
            owner=account.owner,
            is_settled=False
        ).order_by('due_date')
        serializer = CommissionDueSerializer(dues, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Dashboard statistics"""
        settings = CommissionSettings.objects.first()
        
        total_earnings = CommissionTransaction.objects.filter(
            status='settled'
        ).aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
        
        total_pending_dues = OwnerCommissionAccount.objects.aggregate(
            Sum('pending_dues')
        )['pending_dues__sum'] or 0
        
        blocked_count = OwnerCommissionAccount.objects.filter(is_blocked=True).count()
        
        return Response({
            'total_commission_earned': float(total_earnings),
            'total_pending_dues': float(total_pending_dues),
            'blocked_owners_count': blocked_count,
            'commission_percentage': float(settings.commission_percentage),
            'block_dues_threshold': float(settings.block_dues_amount),
        })


class PayoutRequestViewSet(viewsets.ModelViewSet):
    """Manage payout requests"""
    queryset = PayoutRequest.objects.all()
    serializer_class = PayoutRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter, DjangoFilterBackend]
    ordering_fields = ['created_at', 'amount']
    filterset_fields = ['status']
    
    def get_queryset(self):
        """Only show owner's own payouts or admin all payouts"""
        if self.request.user.is_staff:
            return PayoutRequest.objects.all()
        return PayoutRequest.objects.filter(owner=self.request.user)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def request_payout(self, request):
        """Request payout"""
        try:
            payout = PayoutService.request_payout(
                request.user,
                request.data.get('amount'),
                request.data.get('bank_account_number'),
                request.data.get('bank_ifsc_code'),
                request.data.get('bank_holder_name')
            )
            serializer = self.get_serializer(payout)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def process_payout(self, request, pk=None):
        """Process a payout (admin only)"""
        try:
            payout = PayoutService.process_payout(pk, request.user)
            serializer = self.get_serializer(payout)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reject_payout(self, request, pk=None):
        """Reject a payout (admin only)"""
        try:
            payout = PayoutService.reject_payout(
                pk,
                request.data.get('reason'),
                request.user
            )
            serializer = self.get_serializer(payout)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )