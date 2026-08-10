from django.urls import path

from .views import ContactSubmissionAPIView


urlpatterns = [
    path("", ContactSubmissionAPIView.as_view(), name="contact-submit"),
]
