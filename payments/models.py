# ==================== PAYMENTS/MODELS.PY (COMPLETE) ====================
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class CommissionSettings(models.Model):
    """Global commission settings for the platform"""
    commission_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Commission percentage (0-100%)"
    )
    minimum_commission = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=50,
        help_text="Minimum commission amount per transaction"
    )
    payment_processing_fee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.5,
        help_text="Additional processing fee percentage"
    )
    due_days_threshold = models.IntegerField(
        default=30,
        help_text="Days before marking owner as having dues"
    )
    block_after_days = models.IntegerField(
        default=60,
        help_text="Days of dues before blocking owner"
    )
    block_dues_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10000,
        help_text="Block owner if dues exceed this amount"
    )
    auto_settle_enabled = models.BooleanField(
        default=True,
        help_text="Auto settle dues from payments"
    )
    refund_days = models.IntegerField(
        default=7,
        help_text="Days within which refund can be processed"
    )
    refund_charges_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.0,
        help_text="Percentage charges for refund"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Commission Settings"

    def __str__(self):
        return f"Commission: {self.commission_percentage}% | Block Amount: ₹{self.block_dues_amount}"


class OwnerCommissionAccount(models.Model):
    """Track owner's commission account and dues"""
    ACCOUNT_STATUS_CHOICES = (
        ('active', 'Active'),
        ('blocked', 'Blocked'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    )

    owner = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='commission_account'
    )
    
    # Balance tracking
    total_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_commission_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Dues tracking (from COD payments)
    pending_dues = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    settled_dues = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overdue_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    account_status = models.CharField(
        max_length=20, 
        choices=ACCOUNT_STATUS_CHOICES, 
        default='active'
    )
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.CharField(max_length=500, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    unblocked_at = models.DateTimeField(null=True, blank=True)
    
    # Bank details for payout
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_ifsc_code = models.CharField(max_length=20, null=True, blank=True)
    bank_holder_name = models.CharField(max_length=200, null=True, blank=True)
    bank_verified = models.BooleanField(default=False)
    
    # Last payout
    last_payout_date = models.DateTimeField(null=True, blank=True)
    last_payout_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Compliance
    tax_id_number = models.CharField(max_length=50, null=True, blank=True, help_text="PAN/TAN")
    tax_verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Owner Commission Account"
        verbose_name_plural = "Owner Commission Accounts"
        indexes = [
            models.Index(fields=['owner', 'is_blocked']),
            models.Index(fields=['account_status']),
            models.Index(fields=['updated_at']),
        ]

    def __str__(self):
        status_badge = "BLOCKED" if self.is_blocked else "ACTIVE"
        return f"{self.owner.username} - {status_badge} - Balance: ₹{self.current_balance}"

    def check_and_update_block_status(self):
        """Check if owner should be blocked based on dues"""
        settings = CommissionSettings.objects.first()
        if not settings:
            return False

        if self.pending_dues >= settings.block_dues_amount:
            if not self.is_blocked:
                self.is_blocked = True
                self.account_status = 'blocked'
                self.blocked_reason = f"Dues exceed ₹{settings.block_dues_amount}"
                self.blocked_at = timezone.now()
                self.save()
                logger.warning(f"Owner {self.owner.username} blocked due to outstanding dues: ₹{self.pending_dues}")
            return True
        
        return False

    def unblock(self, reason=""):
        """Unblock owner"""
        self.is_blocked = False
        self.account_status = 'active'
        self.blocked_reason = ""
        self.blocked_at = None
        self.unblocked_at = timezone.now()
        self.save()
        logger.info(f"Owner {self.owner.username} unblocked. Reason: {reason}")

    def settle_pending_dues(self, amount):
        """Settle pending dues"""
        settled = min(self.pending_dues, amount)
        self.pending_dues -= settled
        self.settled_dues += settled
        self.current_balance += settled
        self.save()
        return settled


class CommissionTransaction(models.Model):
    """Track all commission transactions"""
    TRANSACTION_TYPE_CHOICES = (
        ('booking_commission', 'Booking Commission'),
        ('cod_collection', 'COD Collection'),
        ('razorpay_payment', 'Razorpay Payment'),
        ('due_settlement', 'Due Settlement'),
        ('adjustment', 'Manual Adjustment'),
        ('refund', 'Refund'),
        ('reversal', 'Reversal'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('settled', 'Settled'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
    )

    owner = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='commission_transactions'
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commission_transaction'
    )
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commission_transaction'
    )
    
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPE_CHOICES)
    
    # Financial details
    booking_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processing_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['booking']),
            models.Index(fields=['status']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"{self.owner.username} - {self.transaction_type} - ₹{self.net_amount}"

    def calculate_commission(self, booking_amount, settings=None):
        """Calculate commission and fees"""
        if not settings:
            settings = CommissionSettings.objects.first()
        
        if not settings:
            return

        commission = (Decimal(booking_amount) * Decimal(settings.commission_percentage)) / Decimal(100)
        commission = max(commission, Decimal(settings.minimum_commission))

        processing_fee = (Decimal(booking_amount) * Decimal(settings.payment_processing_fee)) / Decimal(100)

        net_amount = Decimal(booking_amount) - commission - processing_fee

        self.booking_amount = Decimal(booking_amount)
        self.commission_percentage = settings.commission_percentage
        self.commission_amount = commission
        self.processing_fee = processing_fee
        self.net_amount = max(net_amount, Decimal(0))


class CommissionDue(models.Model):
    """Track pending dues (mainly from COD payments)"""
    AGING_CHOICES = (
        ('0_30', '0-30 Days'),
        ('31_60', '31-60 Days'),
        ('61_90', '61-90 Days'),
        ('90_plus', '90+ Days'),
    )

    owner = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='commission_dues'
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    due_amount = models.DecimalField(max_digits=15, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Status
    is_settled = models.BooleanField(default=False)
    settled_via_transaction = models.ForeignKey(
        CommissionTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settled_dues'
    )
    
    # Dates
    due_date = models.DateField()
    expected_payment_date = models.DateField()
    actual_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Aging
    days_overdue = models.IntegerField(default=0)
    aging_bucket = models.CharField(max_length=20, choices=AGING_CHOICES, default='0_30')
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['owner', 'is_settled']),
            models.Index(fields=['due_date']),
            models.Index(fields=['aging_bucket']),
        ]

    def __str__(self):
        status = "✅ Settled" if self.is_settled else f"⏳ Pending ({self.days_overdue} days)"
        return f"{self.owner.username} - ₹{self.due_amount} ({status})"

    def update_days_overdue(self):
        """Update days overdue and aging bucket"""
        days = (timezone.now().date() - self.expected_payment_date).days
        self.days_overdue = max(0, days)
        
        if days <= 30:
            self.aging_bucket = '0_30'
        elif days <= 60:
            self.aging_bucket = '31_60'
        elif days <= 90:
            self.aging_bucket = '61_90'
        else:
            self.aging_bucket = '90_plus'
        
        self.save()


class Payment(models.Model):
    """Payment records for bookings"""
    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash On Delivery'),
        ('razorpay', 'Razorpay'),
        ('wallet', 'Wallet'),
    )

    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    
    # Razorpay
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True, unique=True, db_index=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)
    
    # COD
    payment_collected_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_payments'
    )
    payment_collected_at = models.DateTimeField(null=True, blank=True)
    
    # Gateway response
    gateway_response = models.JSONField(null=True, blank=True)
    
    # Commission tracking
    has_commission_applied = models.BooleanField(default=False)
    commission_settled = models.BooleanField(default=False)
    settlement_date = models.DateTimeField(null=True, blank=True)
    
    # COD dues
    cod_due_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cod_due_created = models.DateTimeField(null=True, blank=True)
    
    # Idempotency
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['idempotency_key']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.booking.id} - {self.status}"


class Refund(models.Model):
    """Refund management"""
    REASON_CHOICES = (
        ('booking_cancelled', 'Booking Cancelled'),
        ('space_unavailable', 'Space Became Unavailable'),
        ('customer_request', 'Customer Request'),
        ('payment_error', 'Payment Error'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('quality_issue', 'Quality/Service Issue'),
    )
    
    REFUND_STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='refund')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Gateway
    razorpay_refund_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='initiated')
    
    # Notes
    notes = models.TextField(blank=True)
    refunded_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunded_payments'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payment']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Refund for Payment {self.payment.id} - ₹{self.net_refund_amount}"


class PayoutRequest(models.Model):
    """Payout requests from owners"""
    PAYOUT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    )

    owner = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='payout_requests'
    )
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending')
    
    # Bank details (can be different per payout)
    bank_account_number = models.CharField(max_length=50)
    bank_ifsc_code = models.CharField(max_length=20)
    bank_holder_name = models.CharField(max_length=200)
    
    # Processing
    processed_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_payouts'
    )
    
    # Gateway
    razorpay_payout_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    gateway_response = models.JSONField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Payout {self.id} - {self.owner.username} - ₹{self.amount} - {self.status}"