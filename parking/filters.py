# ============================= PARKING/FILTERS.PY =============================
import django_filters
from .models import ParkingSpace


class ParkingSpaceFilter(django_filters.FilterSet):
    """Advanced filtering for parking spaces"""
    
    price_min = django_filters.NumberFilter(
        field_name='price_per_day',
        lookup_expr='gte',
        label='Minimum Price Per Day'
    )
    price_max = django_filters.NumberFilter(
        field_name='price_per_day',
        lookup_expr='lte',
        label='Maximum Price Per Day'
    )
    
    has_security = django_filters.BooleanFilter(
        field_name='has_security_camera',
        label='Has Security Camera'
    )
    has_light = django_filters.BooleanFilter(
        field_name='has_lighting',
        label='Has Lighting'
    )
    has_ev = django_filters.BooleanFilter(
        field_name='has_ev_charging',
        label='Has EV Charging'
    )
    has_surveillance = django_filters.BooleanFilter(
        field_name='has_surveillance',
        label='Has Surveillance'
    )
    has_covered = django_filters.BooleanFilter(
        field_name='has_covered',
        label='Is Covered'
    )
    has_24_7 = django_filters.BooleanFilter(
        field_name='has_24_7_access',
        label='24/7 Access'
    )
    
    rating_min = django_filters.NumberFilter(
        field_name='rating',
        lookup_expr='gte',
        label='Minimum Rating'
    )
    
    space_type = django_filters.MultipleChoiceFilter(
        choices=ParkingSpace.SPACE_TYPE_CHOICES,
        widget=django_filters.widgets.BooleanWidget()
    )
    
    class Meta:
        model = ParkingSpace
        fields = {
            'city': ['exact', 'icontains'],
            'area': ['icontains'],
            'space_type': ['exact'],
            'status': ['exact'],
            'created_at': ['gte', 'lte'],
        }