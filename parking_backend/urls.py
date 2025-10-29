"""
URL configuration for parking_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# ==================== PARKING_BACKEND/URLS.PY ====================
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from users.views import UserViewSet, DriverVehicleViewSet
from parking.views import ParkingSpaceViewSet
from bookings.views import BookingViewSet, ReviewViewSet
from payments.views import PaymentViewSet
from disputes.views import DisputeViewSet
from payments.webhooks import razorpay_webhook

# Create router and register viewsets
router = DefaultRouter()
router.register(r'parking-spaces', ParkingSpaceViewSet, basename='parking-space')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'vehicles', DriverVehicleViewSet, basename='vehicle')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'disputes', DisputeViewSet, basename='disputes')

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API versioning
    path('api/v1/', include([
        # Authentication endpoints
        path('auth/', include([
            path('register/', UserViewSet.as_view({'post': 'register'}), name='register'),
            path('login/', UserViewSet.as_view({'post': 'login'}), name='login'),
            path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
            path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
            path('profile/', UserViewSet.as_view({'get': 'profile', 'put': 'profile'}), name='profile'),
        ])),
        
        # API routes
        path('', include(router.urls)),
        
        # Payments
        path('payments/', include([
            path('initiate/', PaymentViewSet.as_view({'post': 'initiate_payment'}), name='initiate_payment'),
            path('verify/', PaymentViewSet.as_view({'post': 'verify_payment'}), name='verify_payment'),
            path('status/', PaymentViewSet.as_view({'get': 'payment_status'}), name='payment_status'),
        ])),
    ])),

    path('webhooks/', include([
        path('razorpay/payment/', razorpay_webhook, name='razorpay_webhook'),
    ])),
    
    # Serve media files
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)