# ==================== PAYMENTS/SERIALIZERS.PY ====================
from rest_framework import serializers
from django.utils import timezone
from .models import (
    Payment, Refund, CommissionSettings, OwnerCommissionAccount,
    CommissionTransaction, CommissionDue, PayoutRequest
)


class PaymentSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(source='booking.id', read_only=True)
    driver_name = serializers.CharField(source='booking.driver.get_full_name', read_only=True)
    parking_space = serializers.CharField(source='booking.parking_space.title', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'booking_id', 'amount', 'payment_method', 'status',
            'driver_name', 'parking_space', 'razorpay_order_id',
            'razorpay_payment_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentInitiateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=['cod', 'razorpay', 'wallet'])


class PaymentVerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class RefundSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    booking_id = serializers.IntegerField(source='payment.booking.id', read_only=True)
    driver_name = serializers.CharField(source='payment.booking.driver.get_full_name', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment_id', 'booking_id', 'reason', 'refund_amount',
            'refund_charges', 'net_refund_amount', 'status',
            'driver_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'refund_charges', 'net_refund_amount', 'created_at']


class RefundInitiateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    reason = serializers.ChoiceField(choices=[
        'booking_cancelled', 'space_unavailable', 'customer_request',
        'payment_error', 'dispute_resolved', 'quality_issue'
    ])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)


class CommissionSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionSettings
        fields = [
            'id', 'commission_percentage', 'minimum_commission',
            'payment_processing_fee', 'due_days_threshold',
            'block_after_days', 'block_dues_amount', 'auto_settle_enabled',
            'refund_days', 'refund_charges_percentage', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class CommissionTransactionSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    booking_id = serializers.IntegerField(source='booking.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CommissionTransaction
        fields = [
            'id', 'owner_name', 'booking_id', 'transaction_type',
            'booking_amount', 'commission_percentage', 'commission_amount',
            'processing_fee', 'net_amount', 'status', 'notes',
            'created_at', 'settled_at'
        ]
        read_only_fields = ['created_at', 'settled_at']


class CommissionDueSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    booking_id = serializers.IntegerField(source='booking.id', read_only=True, allow_null=True)
    
    class Meta:
        model = CommissionDue
        fields = [
            'id', 'owner_name', 'booking_id', 'due_amount',
            'commission_amount', 'is_settled', 'due_date',
            'expected_payment_date', 'days_overdue', 'aging_bucket'
        ]
        read_only_fields = [
            'id', 'owner_name', 'booking_id', 'days_overdue',
            'aging_bucket', 'created_at'
        ]


class OwnerCommissionAccountSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)
    owner_id = serializers.IntegerField(source='owner.id', read_only=True)
    
    class Meta:
        model = OwnerCommissionAccount
        fields = [
            'id', 'owner_id', 'owner_name', 'owner_email',
            'total_earned', 'total_commission_deducted', 'current_balance',
            'pending_dues', 'settled_dues', 'overdue_amount',
            'account_status', 'is_blocked', 'blocked_reason',
            'blocked_at', 'unblocked_at', 'last_payout_date',
            'last_payout_amount', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_earned', 'total_commission_deducted',
            'current_balance', 'pending_dues', 'settled_dues',
            'created_at', 'updated_at'
        ]


class PayoutRequestSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'owner_name', 'amount', 'status',
            'bank_account_number', 'bank_ifsc_code', 'bank_holder_name',
            'razorpay_payout_id', 'rejection_reason',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'owner_name', 'status', 'razorpay_payout_id',
            'created_at', 'updated_at', 'completed_at'
        ]
