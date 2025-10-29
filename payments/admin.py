# ==================== FILE 1: payments/admin.py (ENHANCED) ====================
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.urls import path
from django.template.response import TemplateResponse
from django.utils import timezone
from datetime import timedelta
from .models import (
    Payment, Refund, CommissionSettings, OwnerCommissionAccount,
    CommissionTransaction, CommissionDue, PayoutRequest
)

class CommissionSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'commission_percentage', 'minimum_commission', 
        'block_dues_amount', 'due_days_threshold'
    ]
    fieldsets = (
        ('Commission', {
            'fields': ('commission_percentage', 'minimum_commission', 'payment_processing_fee')
        }),
        ('Due Management', {
            'fields': ('due_days_threshold', 'block_after_days', 'block_dues_amount', 'auto_settle_enabled')
        }),
        ('Refunds', {
            'fields': ('refund_days', 'refund_charges_percentage')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one CommissionSettings object
        return not CommissionSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'booking_link', 'driver_name', 'amount', 
        'payment_method', 'status_badge', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['booking__id', 'booking__driver__username', 'razorpay_payment_id']
    readonly_fields = ['created_at', 'updated_at', 'razorpay_order_id', 'razorpay_payment_id']
    
    def booking_link(self, obj):
        return f"Booking #{obj.booking.id}"
    booking_link.short_description = 'Booking'
    
    def driver_name(self, obj):
        return obj.booking.driver.get_full_name()
    driver_name.short_description = 'Driver'
    
    def status_badge(self, obj):
        colors = {
            'initiated': 'gray',
            'pending': 'orange',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'booking_id', 'driver_name', 'refund_amount', 
        'refund_charges', 'net_refund_amount', 'status', 'created_at'
    ]
    list_filter = ['status', 'reason', 'created_at']
    search_fields = ['payment__booking__id', 'payment__booking__driver__username']
    readonly_fields = ['created_at', 'updated_at', 'razorpay_refund_id']
    
    def booking_id(self, obj):
        return obj.payment.booking.id
    
    def driver_name(self, obj):
        return obj.payment.booking.driver.get_full_name()
    driver_name.short_description = 'Driver'
    
    def has_add_permission(self, request):
        return False


class CommissionTransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'owner_name', 'transaction_type', 'booking_amount',
        'commission_amount', 'net_amount', 'status', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['owner__username', 'booking__id']
    readonly_fields = [
        'created_at', 'updated_at', 'settled_at',
        'booking_amount', 'commission_amount', 'net_amount'
    ]
    
    def owner_name(self, obj):
        return obj.owner.get_full_name()
    owner_name.short_description = 'Owner'
    
    def has_add_permission(self, request):
        return False


class CommissionDueInline(admin.TabularInline):
    model = CommissionDue
    extra = 0
    fields = ['booking', 'due_amount', 'is_settled', 'due_date', 'aging_bucket']
    readonly_fields = ['booking', 'due_amount', 'created_at', 'aging_bucket']
    
    def has_add_permission(self, request, obj=None):
        return False


class OwnerCommissionAccountAdmin(admin.ModelAdmin):
    list_display = [
        'owner_name', 'balance_display', 'pending_dues_display', 
        'account_status', 'blocked_status', 'last_payout_date'
    ]
    list_filter = ['account_status', 'is_blocked', 'updated_at']
    search_fields = ['owner__username', 'owner__email']
    readonly_fields = [
        'owner', 'total_earned', 'total_commission_deducted',
        'current_balance', 'pending_dues', 'settled_dues',
        'created_at', 'updated_at'
    ]
    
    inlines = [CommissionDueInline]
    
    fieldsets = (
        ('Owner Info', {
            'fields': ('owner',)
        }),
        ('Balance Summary', {
            'fields': (
                'total_earned', 'total_commission_deducted',
                'current_balance', 'pending_dues', 'settled_dues'
            )
        }),
        ('Account Status', {
            'fields': (
                'account_status', 'is_blocked', 'blocked_reason',
                'blocked_at', 'unblocked_at'
            )
        }),
        ('Bank Details', {
            'fields': (
                'bank_account_number', 'bank_ifsc_code',
                'bank_holder_name', 'bank_verified'
            )
        }),
        ('Compliance', {
            'fields': ('tax_id_number', 'tax_verified')
        }),
        ('Payout Info', {
            'fields': ('last_payout_date', 'last_payout_amount'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['block_owner_action', 'unblock_owner_action']
    
    def owner_name(self, obj):
        return obj.owner.get_full_name()
    owner_name.short_description = 'Owner'
    
    def balance_display(self, obj):
        color = 'green' if obj.current_balance >= 0 else 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">₹{:,.2f}</span>',
            color, obj.current_balance
        )
    balance_display.short_description = 'Current Balance'
    
    def pending_dues_display(self, obj):
        if obj.pending_dues > 0:
            return format_html(
                '<span style="color: orange; font-weight: bold;">₹{:,.2f}</span>',
                obj.pending_dues
            )
        return '₹0.00'
    pending_dues_display.short_description = 'Pending Dues'
    
    def blocked_status(self, obj):
        if obj.is_blocked:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">BLOCKED</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 3px 10px; border-radius: 3px;">ACTIVE</span>'
        )
    blocked_status.short_description = 'Status'
    
    def block_owner_action(self, request, queryset):
        reason = request.POST.get('block_reason', 'Admin action')
        for account in queryset:
            if not account.is_blocked:
                account.is_blocked = True
                account.account_status = 'blocked'
                account.blocked_reason = reason
                account.blocked_at = timezone.now()
                account.save()
        self.message_user(request, "Selected owners have been blocked.")
    block_owner_action.short_description = "Block selected owners"
    
    def unblock_owner_action(self, request, queryset):
        for account in queryset:
            if account.is_blocked:
                account.unblock("Admin action")
        self.message_user(request, "Selected owners have been unblocked.")
    unblock_owner_action.short_description = "Unblock selected owners"
    
    def has_add_permission(self, request):
        return False
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.commission_dashboard), name='commission_dashboard'),
        ]
        return custom_urls + urls
    
    def commission_dashboard(self, request):
        """Custom admin dashboard view"""
        from django.db.models import Sum, Count, Avg, Q
        from datetime import timedelta
        
        # Calculate metrics
        total_earnings = CommissionTransaction.objects.filter(
            status='settled'
        ).aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
        
        total_payable = CommissionTransaction.objects.filter(
            status='settled'
        ).aggregate(Sum('net_amount'))['net_amount__sum'] or 0
        
        total_pending_dues = OwnerCommissionAccount.objects.aggregate(
            Sum('pending_dues')
        )['pending_dues__sum'] or 0
        
        blocked_count = OwnerCommissionAccount.objects.filter(is_blocked=True).count()
        total_owners = OwnerCommissionAccount.objects.count()
        
        # Recent transactions
        recent_transactions = CommissionTransaction.objects.all().order_by('-created_at')[:10]
        
        # Overdue owners
        overdue_owners = OwnerCommissionAccount.objects.filter(
            pending_dues__gt=0
        ).order_by('-pending_dues')[:5]
        
        # Aging buckets
        aging_data = CommissionDue.objects.filter(
            is_settled=False
        ).values('aging_bucket').annotate(
            count=Count('id'),
            total_amount=Sum('due_amount')
        )
        
        context = {
            'title': 'Commission Dashboard',
            'total_earnings': total_earnings,
            'total_payable': total_payable,
            'total_pending_dues': total_pending_dues,
            'blocked_owners': blocked_count,
            'total_owners': total_owners,
            'active_owners': total_owners - blocked_count,
            'recent_transactions': recent_transactions,
            'overdue_owners': overdue_owners,
            'aging_data': aging_data,
        }
        
        return TemplateResponse(request, "admin/commission_dashboard.html", context)


class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'owner_name', 'amount', 'status_badge', 
        'bank_account_number', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['owner__username', 'bank_account_number']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'razorpay_payout_id']
    
    fieldsets = (
        ('Owner & Amount', {
            'fields': ('owner', 'amount', 'status')
        }),
        ('Bank Details', {
            'fields': (
                'bank_account_number', 'bank_ifsc_code',
                'bank_holder_name'
            )
        }),
        ('Processing', {
            'fields': (
                'processed_by', 'razorpay_payout_id',
                'notes', 'rejection_reason'
            )
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_payout_action', 'reject_payout_action']
    
    def owner_name(self, obj):
        return obj.owner.get_full_name()
    owner_name.short_description = 'Owner'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'approved': 'blue',
            'processing': 'yellow',
            'completed': 'green',
            'failed': 'red',
            'rejected': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def approve_payout_action(self, request, queryset):
        from payments.services import PayoutService
        for payout in queryset.filter(status='pending'):
            try:
                PayoutService.process_payout(payout.id, request.user)
            except Exception as e:
                self.message_user(request, f"Error processing payout {payout.id}: {str(e)}", level='error')
        self.message_user(request, "Payouts have been approved and sent for processing.")
    approve_payout_action.short_description = "Approve and process selected payouts"
    
    def reject_payout_action(self, request, queryset):
        from payments.services import PayoutService
        for payout in queryset.filter(status='pending'):
            reason = request.POST.get('rejection_reason', 'Rejected by admin')
            PayoutService.reject_payout(payout.id, reason, request.user)
        self.message_user(request, "Selected payouts have been rejected.")
    reject_payout_action.short_description = "Reject selected payouts"


# Register all models
admin.site.register(CommissionSettings, CommissionSettingsAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Refund, RefundAdmin)
admin.site.register(CommissionTransaction, CommissionTransactionAdmin)
admin.site.register(OwnerCommissionAccount, OwnerCommissionAccountAdmin)
admin.site.register(PayoutRequest, PayoutRequestAdmin)
