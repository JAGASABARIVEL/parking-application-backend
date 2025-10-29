# ==================== FILE 2: payments/tasks.py (NEW CELERY TASKS) ====================
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

@shared_task
def settle_pending_cod_payments():
    """Auto-settle COD payments after X days"""
    from .models import CommissionDue, CommissionSettings
    
    settings = CommissionSettings.objects.first()
    if not settings:
        return
    
    threshold_date = (timezone.now() - timedelta(days=settings.due_days_threshold)).date()
    pending_dues = CommissionDue.objects.filter(
        is_settled=False,
        due_date__lte=threshold_date
    )
    
    for due in pending_dues:
        due.update_days_overdue()
        logger.info(f"Updated aging for due {due.id}: {due.aging_bucket}")


@shared_task
def auto_block_owners_with_overdue_dues():
    """Automatically block owners with overdue dues"""
    from .models import OwnerCommissionAccount, CommissionSettings
    
    settings = CommissionSettings.objects.first()
    if not settings:
        return
    
    accounts = OwnerCommissionAccount.objects.filter(pending_dues__gte=settings.block_dues_amount)
    
    for account in accounts:
        if not account.is_blocked:
            account.check_and_update_block_status()
            logger.warning(f"Owner {account.owner.username} auto-blocked due to overdue dues")


@shared_task
def send_commission_due_notifications():
    """Send notifications for upcoming commission dues"""
    from .models import CommissionDue
    from django.core.mail import send_mail
    
    upcoming_dues = CommissionDue.objects.filter(
        is_settled=False,
        expected_payment_date__gte=timezone.now().date(),
        expected_payment_date__lte=(timezone.now() + timedelta(days=3)).date()
    )
    
    for due in upcoming_dues:
        owner = due.owner
        try:
            send_mail(
                subject=f'Commission Due Reminder - ₹{due.due_amount}',
                message=f'''
                Your commission payment is due on {due.expected_payment_date}.
                Amount: ₹{due.due_amount}
                Booking: {due.booking.id if due.booking else 'N/A'}
                
                Please settle this amount to avoid account blocking.
                ''',
                from_email='noreply@parkingapp.com',
                recipient_list=[owner.email],
                fail_silently=False,
            )
            logger.info(f"Due notification sent to {owner.username}")
        except Exception as e:
            logger.error(f"Error sending due notification: {str(e)}")


@shared_task
def reconcile_razorpay_payments():
    """Reconcile payments with Razorpay"""
    from .models import Payment
    import razorpay
    from django.conf import settings as django_settings
    
    try:
        client = razorpay.Client(
            auth=(django_settings.RAZORPAY_KEY_ID, django_settings.RAZORPAY_KEY_SECRET)
        )
        
        # Check pending payments
        pending = Payment.objects.filter(status='pending').order_by('-created_at')[:100]
        
        for payment in pending:
            if payment.razorpay_payment_id:
                try:
                    rzp_payment = client.payment.fetch(payment.razorpay_payment_id)
                    
                    if rzp_payment['status'] == 'captured':
                        payment.status = 'completed'
                        payment.save()
                        logger.info(f"Payment reconciled: {payment.razorpay_payment_id}")
                    elif rzp_payment['status'] == 'failed':
                        payment.status = 'failed'
                        payment.save()
                except Exception as e:
                    logger.error(f"Error reconciling payment: {str(e)}")
    except Exception as e:
        logger.error(f"Razorpay reconciliation error: {str(e)}")


@shared_task
def check_refund_status():
    """Check status of pending refunds"""
    from .models import Refund
    import razorpay
    from django.conf import settings as django_settings
    
    try:
        client = razorpay.Client(
            auth=(django_settings.RAZORPAY_KEY_ID, django_settings.RAZORPAY_KEY_SECRET)
        )
        
        pending_refunds = Refund.objects.filter(status='processing').order_by('-created_at')[:50]
        
        for refund in pending_refunds:
            if refund.razorpay_refund_id:
                try:
                    rzp_refund = client.refund.fetch(refund.razorpay_refund_id)
                    
                    if rzp_refund['status'] == 'processed':
                        refund.status = 'completed'
                        refund.completed_at = timezone.now()
                        refund.save()
                        logger.info(f"Refund completed: {refund.razorpay_refund_id}")
                except Exception as e:
                    logger.error(f"Error checking refund: {str(e)}")
    except Exception as e:
        logger.error(f"Refund status check error: {str(e)}")