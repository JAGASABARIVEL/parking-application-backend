# ==================== PAYMENTS/SERIALIZERS.PY ====================
from rest_framework import serializers
from .models import (CommissionSettings, OwnerCommissionAccount, 
                     CommissionTransaction, CommissionDue,
                     Payment, Refund)


class CommissionSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionSettings
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class OwnerCommissionAccountSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)
    
    class Meta:
        model = OwnerCommissionAccount
        fields = [
            'id', 'owner_name', 'owner_email', 'total_earned', 
            'total_commission_deducted', 'current_balance', 'pending_dues', 
            'is_blocked', 'blocked_reason', 'last_payout_date', 'last_payout_amount'
        ]
        read_only_fields = ['total_earned', 'total_commission_deducted', 'current_balance']


class CommissionTransactionSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    booking_id = serializers.CharField(source='booking.id', read_only=True)
    
    class Meta:
        model = CommissionTransaction
        fields = [
            'id', 'owner_name', 'booking_id', 'transaction_type', 
            'booking_amount', 'commission_percentage', 'commission_amount',
            'processing_fee', 'net_amount', 'status', 'created_at', 'settled_at'
        ]
        read_only_fields = ['created_at', 'settled_at']


class CommissionDueSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    booking_id = serializers.CharField(source='booking.id', read_only=True)
    
    class Meta:
        model = CommissionDue
        fields = [
            'id', 'owner_name', 'booking_id', 'due_amount', 'commission_amount',
            'is_settled', 'due_date', 'expected_payment_date', 'days_overdue'
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'booking', 'amount', 'payment_method', 'status', 'razorpay_order_id', 
                  'razorpay_payment_id', 'created_at', 'updated_at']
        read_only_fields = ['razorpay_order_id', 'razorpay_payment_id', 'created_at', 'updated_at']


class PaymentInitiateSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=['cod', 'razorpay', 'wallet'])


class PaymentVerifySerializer(serializers.Serializer):
    razorpay_order_id = serializers.CharField()
    razorpay_payment_id = serializers.CharField()
    razorpay_signature = serializers.CharField()


class RefundSerializer(serializers.ModelSerializer):
    class Meta:
        model = Refund
        fields = ['id', 'payment', 'reason', 'refund_amount', 'status', 'created_at']
        read_only_fields = ['status', 'created_at']