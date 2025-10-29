from django.shortcuts import render

# Create your views here.


# ==================== PAYMENTS/VIEWS.PY ====================
from rest_framework import viewsets, status, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
import razorpay
from django.conf import settings
from .models import Payment, Refund, Booking, OwnerCommissionAccount, CommissionTransaction, CommissionDue
from .serializers import (
    PaymentSerializer, PaymentInitiateSerializer, PaymentVerifySerializer, CommissionSettings, CommissionSettingsSerializer, OwnerCommissionAccountSerializer,
    CommissionTransactionSerializer, CommissionDueSerializer)


class PaymentViewSet(viewsets.ViewSet):
    """Handle payment processing and verification"""
    permission_classes = [permissions.IsAuthenticated]
    razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    @action(detail=False, methods=['post'])
    def initiate_payment(self, request):
        """Initiate payment for a booking"""
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            booking = Booking.objects.get(id=serializer.validated_data['booking_id'])
        except Booking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user != booking.driver:
            raise permissions.PermissionDenied()
        
        payment_method = serializer.validated_data['payment_method']
        
        # Create or get payment
        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={'amount': booking.total_price, 'payment_method': payment_method}
        )
        
        if payment_method == 'razorpay':
            # Create Razorpay order
            order_data = {
                'amount': int(booking.total_price * 100),  # Amount in paise
                'currency': 'INR',
                'receipt': f'booking_{booking.id}'
            }
            razorpay_order = self.razorpay_client.order.create(data=order_data)
            payment.razorpay_order_id = razorpay_order['id']
            payment.status = 'initiated'
            payment.save()
            
            return Response({
                'payment_id': payment.id,
                'razorpay_order_id': razorpay_order['id'],
                'amount': booking.total_price,
                'currency': 'INR',
                'key_id': settings.RAZORPAY_KEY_ID
            })
        
        elif payment_method == 'cod':
            payment.status = 'pending'
            payment.save()
            return Response({'message': 'COD selected. Confirm booking to proceed', 'payment_id': payment.id})
    
    @action(detail=False, methods=['post'])
    def verify_payment(self, request):
        """Verify Razorpay payment"""
        serializer = PaymentVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            payment = Payment.objects.get(razorpay_order_id=serializer.validated_data['razorpay_order_id'])
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Verify signature
        try:
            self.razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': serializer.validated_data['razorpay_order_id'],
                'razorpay_payment_id': serializer.validated_data['razorpay_payment_id'],
                'razorpay_signature': serializer.validated_data['razorpay_signature']
            })
        except:
            payment.status = 'failed'
            payment.save()
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Payment successful
        payment.razorpay_payment_id = serializer.validated_data['razorpay_payment_id']
        payment.razorpay_signature = serializer.validated_data['razorpay_signature']
        payment.status = 'completed'
        payment.save()
        
        # Confirm booking
        booking = payment.booking
        booking.status = 'confirmed'
        booking.parking_space.available_spaces -= 1
        booking.save()
        booking.parking_space.save()
        
        return Response({'message': 'Payment verified and booking confirmed', 'payment': PaymentSerializer(payment).data})
    
    @action(detail=False, methods=['get'])
    def payment_status(self, request):
        """Get payment status for a booking"""
        booking_id = request.query_params.get('booking_id')
        try:
            payment = Payment.objects.get(booking_id=booking_id)
            return Response(PaymentSerializer(payment).data)
        except Payment.DoesNotExist:
            return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)


from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
import razorpay

class CommissionSettingsViewSet(viewsets.ModelViewSet):
    """Admin only - Manage commission settings"""
    queryset = CommissionSettings.objects.all()
    serializer_class = CommissionSettingsSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def current_settings(self, request):
        """Get current commission settings"""
        settings = CommissionSettings.objects.first()
        if not settings:
            settings = CommissionSettings.objects.create()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    @action(detail=True, methods=['put'])
    def update_settings(self, request, pk=None):
        """Update commission settings"""
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
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['owner__username', 'owner__email']
    ordering_fields = ['pending_dues', 'current_balance', 'total_earned']

    @action(detail=False, methods=['get'])
    def owners_with_dues(self, request):
        """Get owners with pending dues"""
        accounts = OwnerCommissionAccount.objects.filter(pending_dues__gt=0).order_by('-pending_dues')
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
        account.blocked_reason = reason
        account.blocked_at = timezone.now()
        account.save()
        
        return Response({'message': f'Owner {account.owner.username} blocked', 'account': OwnerCommissionAccountSerializer(account).data})

    @action(detail=True, methods=['post'])
    def unblock_owner(self, request, pk=None):
        """Unblock an owner"""
        account = self.get_object()
        account.unblock()
        
        return Response({'message': f'Owner {account.owner.username} unblocked', 'account': OwnerCommissionAccountSerializer(account).data})

    @action(detail=True, methods=['get'])
    def commission_history(self, request, pk=None):
        """Get commission transaction history for owner"""
        account = self.get_object()
        transactions = CommissionTransaction.objects.filter(owner=account.owner).order_by('-created_at')
        serializer = CommissionTransactionSerializer(transactions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pending_dues(self, request, pk=None):
        """Get pending dues for owner"""
        account = self.get_object()
        dues = CommissionDue.objects.filter(owner=account.owner, is_settled=False)
        serializer = CommissionDueSerializer(dues, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get overall commission dashboard statistics"""
        settings = CommissionSettings.objects.first()
        
        total_earnings = CommissionTransaction.objects.filter(
            status='settled'
        ).aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
        
        pending_dues = OwnerCommissionAccount.objects.aggregate(
            Sum('pending_dues')
        )['pending_dues__sum'] or 0
        
        blocked_owners_count = OwnerCommissionAccount.objects.filter(
            is_blocked=True
        ).count()
        
        owners_with_overdue = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__gt=0
        ).values('owner').distinct().count()
        
        return Response({
            'total_commission_earned': float(total_earnings),
            'total_pending_dues': float(pending_dues),
            'blocked_owners_count': blocked_owners_count,
            'owners_with_overdue': owners_with_overdue,
            'commission_percentage': float(settings.commission_percentage) if settings else 0,
            'block_dues_threshold': float(settings.block_dues_amount) if settings else 0,
        })


class CommissionTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """View commission transactions"""
    queryset = CommissionTransaction.objects.all()
    serializer_class = CommissionTransactionSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['owner', 'transaction_type', 'status', 'created_at']
    ordering_fields = ['created_at', 'commission_amount']
    ordering = ['-created_at']

    @action(detail=False, methods=['get'])
    def monthly_report(self, request):
        """Get monthly commission report"""
        year = request.query_params.get('year', datetime.now().year)
        month = request.query_params.get('month', datetime.now().month)
        
        start_date = datetime(int(year), int(month), 1).date()
        end_date = (datetime(int(year), int(month), 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        end_date = end_date.date()
        
        transactions = CommissionTransaction.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='settled'
        )
        
        total_commission = transactions.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
        total_processing_fees = transactions.aggregate(Sum('processing_fee'))['processing_fee__sum'] or 0
        transaction_count = transactions.count()
        
        return Response({
            'period': f"{start_date} to {end_date}",
            'total_commission': float(total_commission),
            'total_processing_fees': float(total_processing_fees),
            'transaction_count': transaction_count,
            'average_commission': float(total_commission / transaction_count) if transaction_count > 0 else 0,
        })

    @action(detail=False, methods=['get'])
    def pending_settlements(self, request):
        """Get pending settlements"""
        transactions = CommissionTransaction.objects.filter(status='pending').order_by('created_at')
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)


class CommissionDueViewSet(viewsets.ReadOnlyModelViewSet):
    """View commission dues"""
    queryset = CommissionDue.objects.all()
    serializer_class = CommissionDueSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['owner', 'is_settled']

    @action(detail=False, methods=['get'])
    def overdue_list(self, request):
        """Get overdue commission dues"""
        dues = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__gt=0
        ).order_by('-days_overdue')
        serializer = self.get_serializer(dues, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def aging_report(self, request):
        """Get aging report of dues"""
        current_0_30 = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__range=[0, 30]
        ).aggregate(Sum('due_amount'))['due_amount__sum'] or 0
        
        current_31_60 = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__range=[31, 60]
        ).aggregate(Sum('due_amount'))['due_amount__sum'] or 0
        
        current_61_90 = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__range=[61, 90]
        ).aggregate(Sum('due_amount'))['due_amount__sum'] or 0
        
        current_90_plus = CommissionDue.objects.filter(
            is_settled=False,
            days_overdue__gt=90
        ).aggregate(Sum('due_amount'))['due_amount__sum'] or 0
        
        return Response({
            'current_0_30_days': float(current_0_30),
            'current_31_60_days': float(current_31_60),
            'current_61_90_days': float(current_61_90),
            'current_90_plus_days': float(current_90_plus),
            'total_overdue': float(current_0_30 + current_31_60 + current_61_90 + current_90_plus),
        })