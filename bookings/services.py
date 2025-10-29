from decimal import Decimal
from django.utils import timezone
from .models import CommissionSettings, OwnerCommissionAccount, CommissionTransaction, CommissionDue, BookingPayout

class CommissionService:
    """Service to handle commission calculations and settlements"""

    @staticmethod
    def get_settings():
        """Get commission settings"""
        settings = CommissionSettings.objects.first()
        if not settings:
            settings = CommissionSettings.objects.create()
        return settings

    @staticmethod
    def check_owner_block_status(owner):
        """Check and update owner block status"""
        try:
            account = OwnerCommissionAccount.objects.get(owner=owner)
            settings = CommissionService.get_settings()
            
            # Check dues threshold
            if account.pending_dues >= settings.block_dues_amount:
                account.check_and_update_block_status()
                return True
            
            return account.is_blocked
        except OwnerCommissionAccount.DoesNotExist:
            return False

    @staticmethod
    def can_owner_receive_payment(owner):
        """Check if owner can receive payments (not blocked)"""
        return not CommissionService.check_owner_block_status(owner)

    @staticmethod
    def process_razorpay_payment(booking, payment):
        """Process Razorpay payment and apply commission"""
        settings = CommissionService.get_settings()
        owner = booking.parking_space.owner
        
        try:
            account, created = OwnerCommissionAccount.objects.get_or_create(owner=owner)
            
            # Create commission transaction
            transaction = CommissionTransaction.objects.create(
                owner=owner,
                booking=booking,
                payment=payment,
                transaction_type='razorpay_payment',
            )
            
            # Calculate commission
            transaction.calculate_commission(booking.total_price, settings)
            transaction.status = 'settled'
            transaction.settled_at = timezone.now()
            transaction.save()
            
            # Settle any pending COD dues
            pending_dues = CommissionDue.objects.filter(owner=owner, is_settled=False).order_by('due_date')
            
            amount_available = transaction.net_amount
            dues_to_settle = []
            
            for due in pending_dues:
                if amount_available >= due.due_amount:
                    due.is_settled = True
                    due.settled_via_transaction = transaction
                    due.actual_payment_date = timezone.now()
                    due.save()
                    dues_to_settle.append(due)
                    amount_available -= due.due_amount
                else:
                    break
            
            # Update account balances
            account.total_earned += booking.total_price
            account.total_commission_deducted += transaction.commission_amount
            account.current_balance += transaction.net_amount
            account.pending_dues -= sum([due.due_amount for due in dues_to_settle])
            account.save()
            
            # Create payout record
            BookingPayout.objects.create(
                booking=booking,
                booking_amount=booking.total_price,
                commission_deducted=transaction.commission_amount,
                processing_fee=transaction.processing_fee,
                owner_payout_amount=transaction.net_amount,
                payout_status='settled',
                payment_method_used='razorpay'
            )
            
            payment.has_commission_applied = True
            payment.commission_settled = True
            payment.settlement_date = timezone.now()
            payment.save()
            
            return transaction
        
        except Exception as e:
            raise Exception(f"Error processing Razorpay payment: {str(e)}")

    @staticmethod
    def process_cod_payment(booking, payment):
        """Process COD payment and create due"""
        settings = CommissionService.get_settings()
        owner = booking.parking_space.owner
        
        try:
            account, created = OwnerCommissionAccount.objects.get_or_create(owner=owner)
            
            # Calculate commission for COD
            transaction = CommissionTransaction.objects.create(
                owner=owner,
                booking=booking,
                payment=payment,
                transaction_type='cod_collection',
            )
            
            transaction.calculate_commission(booking.total_price, settings)
            transaction.status = 'pending'
            transaction.save()
            
            # Create due entry
            due_date = timezone.now().date()
            expected_payment_date = (timezone.now() + timedelta(days=settings.due_days_threshold)).date()
            
            due = CommissionDue.objects.create(
                owner=owner,
                booking=booking,
                due_amount=transaction.net_amount,
                commission_amount=transaction.commission_amount,
                due_date=due_date,
                expected_payment_date=expected_payment_date,
            )
            
            # Update pending dues
            account.pending_dues += transaction.net_amount
            account.total_earned += booking.total_price
            account.total_commission_deducted += transaction.commission_amount
            account.save()
            
            # Check if owner should be blocked
            account.check_and_update_block_status()
            
            # Create payout record
            BookingPayout.objects.create(
                booking=booking,
                booking_amount=booking.total_price,
                commission_deducted=transaction.commission_amount,
                processing_fee=transaction.processing_fee,
                owner_payout_amount=transaction.net_amount,
                payout_status='due_from_cod',
                payment_method_used='cod',
                cod_due_amount=transaction.net_amount,
                cod_due_created=timezone.now()
            )
            
            payment.has_commission_applied = True
            payment.cod_due_amount = transaction.net_amount
            #payment TODO: Complete the remaining code
