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