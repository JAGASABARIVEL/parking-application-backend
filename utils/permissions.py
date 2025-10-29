
# ==================== UTILS/PERMISSIONS.PY ====================
from rest_framework import permissions

class IsOwner(permissions.BasePermission):
    """Permission to check if user is owner of the parking space"""
    
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsDriver(permissions.BasePermission):
    """Permission to check if user is driver who made the booking"""
    
    def has_object_permission(self, request, view, obj):
        return obj.driver == request.user


class IsSpaceOwner(permissions.BasePermission):
    """Permission to check if user owns the parking space"""
    
    def has_object_permission(self, request, view, obj):
        return obj.parking_space.owner == request.user


class IsOwnerOrDriver(permissions.BasePermission):
    """Permission for booking - either owner or driver"""
    
    def has_object_permission(self, request, view, obj):
        return obj.driver == request.user or obj.parking_space.owner == request.user
