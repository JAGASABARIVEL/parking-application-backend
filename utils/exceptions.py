
# ==================== UTILS/EXCEPTIONS.PY ====================
from rest_framework.exceptions import APIException
from rest_framework import status

class ParkingUnavailable(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Parking space is not available for the selected time.'
    default_code = 'parking_unavailable'


class BookingConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Booking conflicts with existing bookings.'
    default_code = 'booking_conflict'


class VehicleNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Vehicle not found or not registered.'
    default_code = 'vehicle_not_found'


class PaymentFailed(APIException):
    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = 'Payment processing failed.'
    default_code = 'payment_failed'