# ==================== PAYMENTS/SERVICES.PY ====================
import razorpay
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from .models import (
    Payment, Refund, CommissionTransaction, CommissionDue,
    CommissionSettings, OwnerCommissionAccount, PayoutRequest
)
from bookings.models import Booking

logger = logging.getLogger(__name__)


class RazorpayService:
    """Razorpay payment gateway integration"""
    
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    
    def create_order(self, booking_id, amount, notes=None):
        """Create Razorpay order"""
        try:
            booking = Booking.objects.get(id=booking_id)
            
            order_data = {
                'amount': int(Decimal(amount) * 100),  # Amount in paise
                'currency': 'INR',
                'receipt': f'booking_{booking_id}_{timezone.now().timestamp()}',
                'notes': notes or {
                    'booking_id': booking_id,
                    'driver': booking.driver.username,
                    'parking_space': booking.parking_space.title,
                }
            }
            
            razorpay_order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {razorpay_order['id']} for booking {booking_id}")
            
            return razorpay_order
        
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {str(e)}")
            raise Exception(f"Failed to create order: {str(e)}")
    
    def verify_payment(self, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        """Verify Razorpay payment signature"""
        try:
            self.client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })
            logger.info(f"Payment verified: {razorpay_payment_id}")
            return True
        
        except razorpay.errors.SignatureVerificationError:
            logger.error(f"Signature verification failed for payment: {razorpay_payment_id}")
            return False
        
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return False
    
    def fetch_payment(self, razorpay_payment_id):
        """Fetch payment details from Razorpay"""
        try:
            payment = self.client.payment.fetch(razorpay_payment_id)
            return payment
        except Exception as e:
            logger.error(f"Error fetching payment: {str(e)}")
            raise
    
    def create_refund(self, razorpay_payment_id, amount=None, notes=None):
        """Create refund for a payment"""
        try:
            refund_data = {}
            if amount:
                refund_data['amount'] = int(Decimal(amount) * 100)
            if notes:
                refund_data['notes'] = notes
            
            refund = self.client.payment.refund(razorpay_payment_id, refund_data)
            logger.info(f"Refund created: {refund['id']} for payment {razorpay_payment_id}")
            
            return refund
        
        except Exception as e:
            logger.error(f"Error creating refund: {str(e)}")
            raise
    
    def fetch_refund(self, refund_id):
        """Fetch refund details"""
        try:
            refund = self.client.refund.fetch(refund_id)
            return refund
        except Exception as e:
            logger.error(f"Error fetching refund: {str(e)}")
            raise
    
    def create_payout(self, account_number, ifsc, amount, notes=None):
        """Create payout to bank account"""
        try:
            payout_data = {
                'account_number': account_number,
                'fund_account': {
                    'account_type': 'bank_account',
                    'bank_account': {
                        'name': notes.get('name', 'Owner') if notes else 'Owner',
                        'notes': notes,
                        'ifsc': ifsc,
                        'account_number': account_number,
                    }
                },
                'amount': int(Decimal(amount) * 100),
                'currency': 'INR',
                'mode': 'NEFT',
            }
            
            payout = self.client.payout.create(payout_data)
            logger.info(f"Payout created: {payout['id']} for amount ₹{amount}")
            
            return payout
        
        except Exception as e:
            logger.error(f"Error creating payout: {str(e)}")
            raise


class CommissionService:
    """Handle all commission-related operations"""
    
    @staticmethod
    def get_settings():
        """Get commission settings"""
        settings = CommissionSettings.objects.first()
        if not settings:
            settings = CommissionSettings.objects.create()
        return settings
    
    @staticmethod
    def get_or_create_account(owner):
        """Get or create owner's commission account"""
        account, created = OwnerCommissionAccount.objects.get_or_create(owner=owner)
        return account
    
    @staticmethod
    @transaction.atomic
    def process_razorpay_payment(booking, payment, razorpay_payment_id):
        """Process successful Razorpay payment and apply commission"""
        settings = CommissionService.get_settings()
        owner = booking.parking_space.owner
        
        try:
            # Get or create account
            account = CommissionService.get_or_create_account(owner)
            
            # Create commission transaction
            trans = CommissionTransaction.objects.create(
                owner=owner,
                booking=booking,
                payment=payment,
                transaction_type='razorpay_payment',
                idempotency_key=f"rzp_{razorpay_payment_id}"
            )
            
            # Calculate commission
            trans.calculate_commission(booking.total_price, settings)
            trans.status = 'settled'
            trans.settled_at = timezone.now()
            trans.save()
            
            # Auto-settle old COD dues
            if settings.auto_settle_enabled:
                pending_dues = CommissionDue.objects.filter(
                    owner=owner,
                    is_settled=False
                ).order_by('due_date')
                
                amount_available = trans.net_amount
                
                for due in pending_dues:
                    if amount_available >= due.due_amount:
                        due.is_settled = True
                        due.settled_via_transaction = trans
                        due.actual_payment_date = timezone.now()
                        due.save()
                        
                        amount_available -= due.due_amount
                        account.pending_dues -= due.due_amount
                        account.settled_dues += due.due_amount
                    else:
                        break
            
            # Update account balances
            account.total_earned += Decimal(booking.total_price)
            account.total_commission_deducted += trans.commission_amount
            account.current_balance += trans.net_amount
            
            # Check if should be unblocked (if dues are settled)
            if account.is_blocked and account.pending_dues < settings.block_dues_amount:
                account.unblock("Dues payment received - Balance restored")
            
            account.save()
            
            # Update payment
            payment.status = 'completed'
            payment.razorpay_payment_id = razorpay_payment_id
            payment.has_commission_applied = True
            payment.commission_settled = True
            payment.settlement_date = timezone.now()
            payment.save()
            
            logger.info(f"Razorpay payment processed for booking {booking.id}: ₹{trans.net_amount} credited to {owner.username}")
            return trans
        
        except Exception as e:
            logger.error(f"Error processing Razorpay payment: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def process_cod_payment(booking, payment):
        """Process COD payment and create due"""
        settings = CommissionService.get_settings()
        owner = booking.parking_space.owner
        
        try:
            account = CommissionService.get_or_create_account(owner)
            
            # Create commission transaction
            trans = CommissionTransaction.objects.create(
                owner=owner,
                booking=booking,
                payment=payment,
                transaction_type='cod_collection',
                idempotency_key=f"cod_{booking.id}_{timezone.now().timestamp()}"
            )
            
            # Calculate commission
            trans.calculate_commission(booking.total_price, settings)
            trans.status = 'pending'
            trans.save()
            
            # Create due entry
            due_date = timezone.now().date()
            expected_payment_date = (timezone.now() + timedelta(days=settings.due_days_threshold)).date()
            
            due = CommissionDue.objects.create(
                owner=owner,
                booking=booking,
                due_amount=trans.net_amount,
                commission_amount=trans.commission_amount,
                due_date=due_date,
                expected_payment_date=expected_payment_date,
            )
            
            # Update account
            account.total_earned += Decimal(booking.total_price)
            account.total_commission_deducted += trans.commission_amount
            account.pending_dues += trans.net_amount
            
            # Check if should be blocked
            if not account.is_blocked:
                account.check_and_update_block_status()
            
            account.save()
            
            # Update payment
            payment.status = 'pending'
            payment.has_commission_applied = True
            payment.cod_due_amount = trans.net_amount
            payment.cod_due_created = timezone.now()
            payment.save()
            
            logger.info(f"COD payment created for booking {booking.id}: Due ₹{due.due_amount} from {owner.username}")
            return trans
        
        except Exception as e:
            logger.error(f"Error processing COD payment: {str(e)}")
            raise
    
    @staticmethod
    def settle_cod_manually(due_id, collected_amount, collected_by):
        """Manually mark COD payment as collected"""
        try:
            due = CommissionDue.objects.get(id=due_id)
            
            if due.is_settled:
                raise Exception("Due already settled")
            
            # Create settlement transaction
            trans = CommissionTransaction.objects.create(
                owner=due.owner,
                booking=due.booking,
                transaction_type='due_settlement',
                booking_amount=due.due_amount,
                net_amount=min(Decimal(collected_amount), due.due_amount),
                status='settled',
                settled_at=timezone.now(),
            )
            trans.save()
            
            # Mark due as settled
            if Decimal(collected_amount) >= due.due_amount:
                due.is_settled = True
                due.actual_payment_date = timezone.now()
                due.settled_via_transaction = trans
            
            due.save()
            
            # Update account
            account = due.owner.commission_account
            account.pending_dues -= min(Decimal(collected_amount), due.due_amount)
            account.settled_dues += min(Decimal(collected_amount), due.due_amount)
            account.current_balance += min(Decimal(collected_amount), due.due_amount)
            
            if not account.is_blocked or account.pending_dues < CommissionService.get_settings().block_dues_amount:
                account.check_and_update_block_status()
            
            account.save()
            
            logger.info(f"COD payment settled for due {due_id}: ₹{collected_amount}")
            return trans
        
        except Exception as e:
            logger.error(f"Error settling COD: {str(e)}")
            raise


class RefundService:
    """Handle refund operations"""
    
    @staticmethod
    @transaction.atomic
    def initiate_refund(payment_id, reason, refund_amount=None, refunded_by=None):
        """Initiate refund for a payment"""
        try:
            payment = Payment.objects.get(id=payment_id)
            settings = CommissionService.get_settings()
            
            # Check if already refunded
            if payment.status == 'refunded':
                raise Exception("Payment already refunded")
            
            if payment.refund.exists():
                raise Exception("Refund already exists for this payment")
            
            # Check refund window
            days_elapsed = (timezone.now().date() - payment.created_at.date()).days
            if days_elapsed > settings.refund_days:
                raise Exception(f"Refund window expired (max {settings.refund_days} days)")
            
            # Calculate refund amount
            actual_refund = Decimal(refund_amount) if refund_amount else payment.amount
            
            # Calculate refund charges
            refund_charges = (actual_refund * Decimal(settings.refund_charges_percentage)) / Decimal(100)
            net_refund = actual_refund - refund_charges
            
            # Create refund record
            refund = Refund.objects.create(
                payment=payment,
                reason=reason,
                refund_amount=actual_refund,
                refund_charges=refund_charges,
                net_refund_amount=net_refund,
                refunded_by=refunded_by,
                status='initiated'
            )
            
            # Process based on payment method
            if payment.payment_method == 'razorpay':
                razorpay_service = RazorpayService()
                try:
                    razorpay_refund = razorpay_service.create_refund(
                        payment.razorpay_payment_id,
                        actual_refund,
                        {'reason': reason, 'refund_id': refund.id}
                    )
                    refund.razorpay_refund_id = razorpay_refund['id']
                    refund.status = 'processing'
                except Exception as e:
                    refund.status = 'failed'
                    logger.error(f"Razorpay refund failed: {str(e)}")
                    raise
            
            elif payment.payment_method == 'cod':
                # For COD, just mark as initiated
                refund.status = 'processing'
            
            refund.save()
            
            # Reverse commission if needed
            RefundService._reverse_commission(payment, net_refund)
            
            payment.status = 'refunded' if Decimal(refund_amount or payment.amount) == payment.amount else 'partially_refunded'
            payment.save()
            
            logger.info(f"Refund initiated for payment {payment_id}: ₹{net_refund}")
            return refund
        
        except Exception as e:
            logger.error(f"Error initiating refund: {str(e)}")
            raise
    
    @staticmethod
    def _reverse_commission(payment, refund_amount):
        """Reverse commission when refund is issued"""
        try:
            trans = CommissionTransaction.objects.get(payment=payment)
            owner = trans.owner
            
            # Calculate proportional commission to reverse
            commission_ratio = Decimal(refund_amount) / Decimal(trans.net_amount) if trans.net_amount > 0 else Decimal(0)
            reversed_commission = trans.commission_amount * commission_ratio
            
            # Create reversal transaction
            reversal = CommissionTransaction.objects.create(
                owner=owner,
                payment=payment,
                transaction_type='reversal',
                net_amount=-refund_amount,
                commission_amount=-reversed_commission,
                status='settled',
                notes=f'Reversal for refund: {refund_amount}'
            )
            
            # Update account
            account = owner.commission_account
            account.current_balance -= refund_amount
            account.total_commission_deducted -= reversed_commission
            account.save()
            
            logger.info(f"Commission reversed for payment {payment.id}: ₹{reversed_commission}")
        
        except Exception as e:
            logger.error(f"Error reversing commission: {str(e)}")
            # Don't raise - refund should complete even if reversal fails


class PayoutService:
    """Handle payout operations for owners"""
    
    @staticmethod
    def request_payout(owner, amount, bank_account_number, bank_ifsc_code, bank_holder_name):
        """Create payout request from owner"""
        try:
            account = CommissionService.get_or_create_account(owner)
            
            # Validate account is not blocked
            if account.is_blocked:
                raise Exception("Cannot request payout - account is blocked")
            
            # Validate sufficient balance
            if Decimal(amount) > account.current_balance:
                raise Exception(f"Insufficient balance. Available: ₹{account.current_balance}")
            
            # Create payout request
            payout = PayoutRequest.objects.create(
                owner=owner,
                amount=amount,
                bank_account_number=bank_account_number,
                bank_ifsc_code=bank_ifsc_code,
                bank_holder_name=bank_holder_name,
                status='pending'
            )
            
            logger.info(f"Payout request created: {payout.id} for {owner.username}: ₹{amount}")
            return payout
        
        except Exception as e:
            logger.error(f"Error creating payout request: {str(e)}")
            raise
    
    @staticmethod
    @transaction.atomic
    def process_payout(payout_id, processed_by=None):
        """Process approved payout"""
        try:
            payout = PayoutRequest.objects.get(id=payout_id)
            
            if payout.status != 'pending':
                raise Exception(f"Payout is {payout.status}, cannot process")
            
            account = payout.owner.commission_account
            
            # Deduct from balance
            if payout.amount > account.current_balance:
                raise Exception("Insufficient balance")
            
            payout.status = 'processing'
            payout.processed_by = processed_by
            payout.save()
            
            # Process via Razorpay
            razorpay_service = RazorpayService()
            try:
                razorpay_payout = razorpay_service.create_payout(
                    payout.bank_account_number,
                    payout.bank_ifsc_code,
                    payout.amount,
                    {'name': payout.bank_holder_name}
                )
                
                payout.razorpay_payout_id = razorpay_payout['id']
                payout.gateway_response = razorpay_payout
                payout.status = 'completed'
                payout.completed_at = timezone.now()
            
            except Exception as e:
                payout.status = 'failed'
                payout.gateway_response = {'error': str(e)}
                raise
            
            finally:
                payout.save()
            
            # Update account balance
            account.current_balance -= payout.amount
            account.last_payout_date = timezone.now()
            account.last_payout_amount = payout.amount
            account.save()
            
            logger.info(f"Payout processed: {payout_id} - ₹{payout.amount} to {payout.owner.username}")
            return payout
        
        except Exception as e:
            logger.error(f"Error processing payout: {str(e)}")
            raise
    
    @staticmethod
    def reject_payout(payout_id, reason, processed_by=None):
        """Reject a payout request"""
        try:
            payout = PayoutRequest.objects.get(id=payout_id)
            
            if payout.status != 'pending':
                raise Exception("Can only reject pending payouts")
            
            payout.status = 'rejected'
            payout.rejection_reason = reason
            payout.processed_by = processed_by
            payout.save()
            
            logger.info(f"Payout rejected: {payout_id} - Reason: {reason}")
            return payout
        
        except Exception as e:
            logger.error(f"Error rejecting payout: {str(e)}")
            raise