# ==================== FILE 1: payments/webhooks.py (NEW) ====================
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
import json
import razorpay
from django.conf import settings
import logging
from .models import Payment, CommissionTransaction, CommissionDue, OwnerCommissionAccount
from .services import CommissionService
from bookings.models import Booking

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """Handle Razorpay payment webhooks"""
    try:
        # Parse webhook data
        webhook_data = json.loads(request.body)
        event = webhook_data.get('event')
        payload = webhook_data.get('payload', {})
        
        # Verify webhook signature
        webhook_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
        if not verify_webhook_signature(request.body, webhook_signature):
            logger.warning(f"Invalid webhook signature: {webhook_signature}")
            return JsonResponse({'status': 'invalid_signature'}, status=400)
        
        # Handle different events
        if event == 'payment.authorized':
            handle_payment_authorized(payload)
        elif event == 'payment.failed':
            handle_payment_failed(payload)
        elif event == 'payment.captured':
            handle_payment_captured(payload)
        elif event == 'refund.created':
            handle_refund_created(payload)
        elif event == 'refund.processed':
            handle_refund_processed(payload)
        elif event == 'payout.processed':
            handle_payout_processed(payload)
        
        return JsonResponse({'status': 'success'})
    
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def verify_webhook_signature(body, signature):
    """Verify Razorpay webhook signature"""
    try:
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        return client.utility.verify_webhook_signature(body, signature, settings.RAZORPAY_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Webhook signature verification error: {str(e)}")
        return False


def handle_payment_authorized(payload):
    """Handle payment.authorized event"""
    payment_data = payload.get('payment', {})
    order_id = payment_data.get('order_id')
    payment_id = payment_data.get('id')
    
    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        payment.status = 'completed'
        payment.razorpay_payment_id = payment_id
        payment.payment_collected_at = timezone.now()
        payment.save()
        
        logger.info(f"Payment authorized: {payment_id} for order {order_id}")
    except Payment.DoesNotExist:
        logger.warning(f"Payment not found for order: {order_id}")


def handle_payment_failed(payload):
    """Handle payment.failed event"""
    payment_data = payload.get('payment', {})
    order_id = payment_data.get('order_id')
    error_description = payment_data.get('error_description', 'Unknown error')
    
    try:
        payment = Payment.objects.get(razorpay_order_id=order_id)
        payment.status = 'failed'
        payment.gateway_response = {'error': error_description}
        payment.save()
        
        logger.warning(f"Payment failed for order {order_id}: {error_description}")
    except Payment.DoesNotExist:
        logger.warning(f"Payment not found for failed order: {order_id}")


def handle_payment_captured(payload):
    """Handle payment.captured event - Process commission"""
    payment_data = payload.get('payment', {})
    payment_id = payment_data.get('id')
    amount = Decimal(payment_data.get('amount', 0)) / 100  # Convert paise to rupees
    
    try:
        payment = Payment.objects.get(razorpay_payment_id=payment_id)
        booking = payment.booking
        
        # Process commission
        if not payment.has_commission_applied:
            CommissionService.process_razorpay_payment(booking, payment, payment_id)
            logger.info(f"Commission processed for payment {payment_id}")
    except Exception as e:
        logger.error(f"Error processing captured payment {payment_id}: {str(e)}")


def handle_refund_created(payload):
    """Handle refund.created event"""
    refund_data = payload.get('refund', {})
    refund_id = refund_data.get('id')
    payment_id = refund_data.get('payment_id')
    
    try:
        payment = Payment.objects.get(razorpay_payment_id=payment_id)
        refund = payment.refund
        refund.razorpay_refund_id = refund_id
        refund.status = 'processing'
        refund.save()
        
        logger.info(f"Refund created: {refund_id} for payment {payment_id}")
    except Exception as e:
        logger.error(f"Error handling refund creation: {str(e)}")


def handle_refund_processed(payload):
    """Handle refund.processed event"""
    refund_data = payload.get('refund', {})
    refund_id = refund_data.get('id')
    status = refund_data.get('status')
    
    try:
        from .models import Refund
        refund = Refund.objects.get(razorpay_refund_id=refund_id)
        
        if status == 'processed':
            refund.status = 'completed'
            refund.completed_at = timezone.now()
        elif status == 'failed':
            refund.status = 'failed'
        
        refund.save()
        logger.info(f"Refund processed: {refund_id} - Status: {status}")
    except Exception as e:
        logger.error(f"Error handling refund processed: {str(e)}")


def handle_payout_processed(payload):
    """Handle payout.processed event"""
    payout_data = payload.get('payout', {})
    payout_id = payout_data.get('id')
    status = payout_data.get('status')
    
    try:
        from .models import PayoutRequest
        payout = PayoutRequest.objects.get(razorpay_payout_id=payout_id)
        
        if status == 'processed':
            payout.status = 'completed'
            payout.completed_at = timezone.now()
        elif status == 'failed':
            payout.status = 'failed'
        
        payout.save()
        logger.info(f"Payout processed: {payout_id} - Status: {status}")
    except Exception as e:
        logger.error(f"Error handling payout: {str(e)}")
