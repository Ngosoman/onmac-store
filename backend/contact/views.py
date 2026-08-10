import logging

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ContactSubmissionSerializer


logger = logging.getLogger(__name__)


class ContactSubmissionAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        serializer = ContactSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = serializer.validated_data
        recipient = str(getattr(settings, "CONTACT_RECEIVER_EMAIL", "onmac.limited@gmail.com")).strip() or "onmac.limited@gmail.com"
        from_email = str(getattr(settings, "DEFAULT_FROM_EMAIL", recipient)).strip() or recipient

        subject = f"[Onmac Contact] {payload['subject']}"
        body_lines = [
            "A new contact request was submitted on the Onmac website.",
            "",
            f"Name: {payload['name']}",
            f"Email: {payload['email']}",
            f"Phone: {payload.get('phone') or 'Not provided'}",
            "",
            "Message:",
            str(payload["message"]),
        ]
        body = "\n".join(body_lines)

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
                reply_to=[payload["email"]],
            )
        except Exception:
            logger.exception("Unable to deliver contact submission email")
            return Response(
                {"detail": ["Unable to send your message right now. Please try again shortly."]},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {"message": "Your message has been sent successfully."},
            status=status.HTTP_201_CREATED,
        )