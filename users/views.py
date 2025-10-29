from django.shortcuts import render

# Create your views here.
# ==================== USERS/VIEWS.PY ====================
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser, DriverVehicle
from .serializers import (UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
                          DriverVehicleSerializer)


class UserViewSet(viewsets.ViewSet):
    """User registration, login, and profile management"""
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserProfileSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'User registered successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """User login"""
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserProfileSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get', 'put'], permission_classes=[permissions.IsAuthenticated])
    def profile(self, request):
        """Get or update user profile"""
        if request.method == 'GET':
            serializer = UserProfileSerializer(request.user)
            return Response(serializer.data)
        
        elif request.method == 'PUT':
            serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DriverVehicleViewSet(viewsets.ModelViewSet):
    """Register and manage driver vehicles"""
    serializer_class = DriverVehicleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DriverVehicle.objects.filter(driver=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(driver=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active_vehicles(self, request):
        """Get list of active vehicles"""
        vehicles = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(vehicles, many=True)
        return Response(serializer.data)
