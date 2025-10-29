# ==================== DISPUTES/MODELS.PY ====================
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class Dispute(models.Model):
    """Track disputes between drivers and owners"""
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('under_review', 'Under Review'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('closed', 'Closed'),
    )
    
    DISPUTE_TYPE_CHOICES = (
        ('payment_issue', 'Payment Issue'),
        ('refund_dispute', 'Refund Dispute'),
        ('quality_issue', 'Quality Issue'),
        ('space_unavailable', 'Space Unavailable'),
        ('damage_claim', 'Damage Claim'),
        ('other', 'Other'),
    )
    
    RESOLUTION_TYPE_CHOICES = (
        ('refund_full', 'Full Refund'),
        ('refund_partial', 'Partial Refund'),
        ('compensation', 'Compensation'),
        ('reinstatement', 'Reinstatement'),
        ('no_action', 'No Action'),
    )

    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='disputes'
    )
    
    # Parties
    raised_by = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='disputes_raised'
    )
    other_party = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='disputes_against'
    )
    
    # Details
    dispute_type = models.CharField(max_length=50, choices=DISPUTE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Evidence
    attachments = models.JSONField(default=list, help_text="List of attachment URLs")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Resolution
    resolution_type = models.CharField(
        max_length=50,
        choices=RESOLUTION_TYPE_CHOICES,
        null=True,
        blank=True
    )
    resolution_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    resolution_notes = models.TextField(blank=True)
    
    # Assignment
    assigned_to = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_disputes'
    )
    
    # Timeline
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking']),
            models.Index(fields=['status']),
            models.Index(fields=['raised_by']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Dispute {self.id} - {self.dispute_type} - {self.status}"


class DisputeComment(models.Model):
    """Comments and updates on disputes"""
    dispute = models.ForeignKey(
        Dispute,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    
    author = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='dispute_comments'
    )
    
    comment = models.TextField()
    attachments = models.JSONField(default=list)
    
    is_internal = models.BooleanField(
        default=False,
        help_text="Only visible to admin"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on Dispute {self.dispute.id} by {self.author.username}"
