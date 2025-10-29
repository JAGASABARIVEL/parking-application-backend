from django.db import models
from bookings.models import Booking
from users.models import CustomUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal

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
        default=0,
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Commission Settings"

    def __str__(self):
        return f"Commission: {self.commission_percentage}%"


class OwnerCommissionAccount(models.Model):
    """Track owner's commission account and dues"""
    owner = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='commission_account'
    )
    
    # Balance tracking
    total_earned = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_commission_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Dues tracking
    pending_dues = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # From COD
    settled_dues = models.DecimalField(max_digits=15, decimal_places=2, default=0)   # Historical settled dues
    
    # Status
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.CharField(max_length=500, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    
    # Bank details for payout
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_ifsc_code = models.CharField(max_length=20, null=True, blank=True)
    bank_holder_name = models.CharField(max_length=200, null=True, blank=True)
    
    # Last payout
    last_payout_date = models.DateTimeField(null=True, blank=True)
    last_payout_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Owner Commission Account"
        verbose_name_plural = "Owner Commission Accounts"

    def __str__(self):
        return f"{self.owner.username} - Balance: ₹{self.current_balance}"

    def check_and_update_block_status(self):
        """Check if owner should be blocked based on dues"""
        settings = CommissionSettings.objects.first()
        if not settings:
            return False

        # Check if dues exceed threshold
        if self.pending_dues >= settings.block_dues_amount:
            self.is_blocked = True
            self.blocked_reason = f"Dues exceed ₹{settings.block_dues_amount}"
            self.blocked_at = timezone.now()
            self.save()
            return True

        # Check if dues are old (past due_days_threshold)
        # This would require a separate aging model or check in CommissionDue
        return False

    def unblock(self, reason=""):
        """Unblock owner"""
        self.is_blocked = False
        self.blocked_reason = ""
        self.blocked_at = None
        self.save()


class CommissionTransaction(models.Model):
    """Track all commission transactions"""
    TRANSACTION_TYPE_CHOICES = (
        ('booking_commission', 'Booking Commission'),
        ('cod_collection', 'COD Collection'),
        ('razorpay_payment', 'Razorpay Payment'),
        ('due_settlement', 'Due Settlement'),
        ('adjustment', 'Manual Adjustment'),
        ('refund', 'Refund'),
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
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPE_CHOICES)
    
    # Financial details
    booking_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    processing_fee = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # Amount owner receives
    
    # Status
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('settled', 'Settled'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ]
    )
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'created_at']),
            models.Index(fields=['booking']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.owner.username} - {self.transaction_type} - ₹{self.commission_amount}"

    def calculate_commission(self, booking_amount, settings=None):
        """Calculate commission and fees"""
        if not settings:
            settings = CommissionSettings.objects.first()
        
        if not settings:
            return

        # Calculate commission
        commission = (booking_amount * Decimal(settings.commission_percentage)) / Decimal(100)
        commission = max(commission, Decimal(settings.minimum_commission))

        # Calculate processing fee
        processing_fee = (booking_amount * Decimal(settings.payment_processing_fee)) / Decimal(100)

        # Calculate net amount owner receives
        net_amount = booking_amount - commission - processing_fee

        self.booking_amount = booking_amount
        self.commission_percentage = settings.commission_percentage
        self.commission_amount = commission
        self.processing_fee = processing_fee
        self.net_amount = net_amount


class CommissionDue(models.Model):
    """Track pending dues (mainly from COD payments)"""
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
    
    # Important dates
    due_date = models.DateField()  # When payment was received
    expected_payment_date = models.DateField()  # Expected settlement date
    actual_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Aging
    days_overdue = models.IntegerField(default=0)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']
        indexes = [
            models.Index(fields=['owner', 'is_settled']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        status = "Settled" if self.is_settled else "Pending"
        return f"{self.owner.username} - ₹{self.due_amount} ({status})"

    def update_days_overdue(self):
        """Update days overdue"""
        days = (timezone.now().date() - self.expected_payment_date).days
        self.days_overdue = max(0, days)
        self.save()

class Payment(models.Model):
    STATUS_CHOICES = (
        ('initiated', 'Initiated'),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash On Delivery'),
        ('razorpay', 'Razorpay'),
        ('wallet', 'Wallet'),
    )

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    
    # For Razorpay
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)
    
    # For COD
    payment_collected_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='collected_payments')
    payment_collected_at = models.DateTimeField(null=True, blank=True)
    
    gateway_response = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    has_commission_applied = models.BooleanField(default=False)
    commission_settled = models.BooleanField(default=False)
    settlement_date = models.DateTimeField(null=True, blank=True)
    
    # For tracking COD due amounts
    cod_due_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cod_due_created = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Payment {self.id} - {self.booking.id}"

class Refund(models.Model):
    REASON_CHOICES = (
        ('booking_cancelled', 'Booking Cancelled'),
        ('space_unavailable', 'Space Became Unavailable'),
        ('customer_request', 'Customer Request'),
        ('payment_error', 'Payment Error'),
    )
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='refund')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    razorpay_refund_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Refund for Payment {self.payment.id}"

