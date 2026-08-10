from rest_framework import serializers


class ContactSubmissionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    subject = serializers.CharField(max_length=180)
    message = serializers.CharField(max_length=4000)
