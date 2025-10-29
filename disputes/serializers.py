
# ==================== DISPUTES/SERIALIZERS.PY ====================

from rest_framework import serializers
from .models import DisputeComment, Dispute

class DisputeCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = DisputeComment
        fields = [
            'id', 'author_name', 'comment', 'attachments',
            'is_internal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author_name', 'created_at', 'updated_at']


class DisputeSerializer(serializers.ModelSerializer):
    raised_by_name = serializers.CharField(source='raised_by.get_full_name', read_only=True)
    other_party_name = serializers.CharField(source='other_party.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True, allow_null=True)
    booking_details = serializers.SerializerMethodField()
    comments = DisputeCommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'booking_details', 'raised_by_name', 'other_party_name',
            'dispute_type', 'title', 'description', 'attachments',
            'status', 'resolution_type', 'resolution_amount', 'resolution_notes',
            'assigned_to_name', 'comments', 'created_at', 'updated_at', 'resolved_at'
        ]
        read_only_fields = [
            'id', 'raised_by_name', 'other_party_name', 'created_at', 'updated_at'
        ]
    
    def get_booking_details(self, obj):
        return {
            'booking_id': obj.booking.id,
            'parking_space': obj.booking.parking_space.title,
            'amount': float(obj.booking.total_price),
            'status': obj.booking.status,
        }
