from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.core.mail import send_mail
from django.conf import settings
from project_review.models import PasswordResetToken


class Command(BaseCommand):
    help = "Generate a password reset token and URL for a given email; optionally send it via email."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="User's email to generate reset link for")
        parser.add_argument("--send", action="store_true", help="Send the reset link to the email")
        parser.add_argument("--base", default="http://127.0.0.1:8000", help="Base URL for building the absolute link")

    def handle(self, *args, **opts):
        email = opts["email"]
        base = opts["base"].rstrip("/")
        do_send = opts["send"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"No account found with email: {email}"))
            return

        # Create persistent token in DB
        token = get_random_string(40)
        PasswordResetToken.objects.create(user=user, token=token)

        path = reverse("project_review:reset_password", args=[token])
        link = f"{base}{path}"

        self.stdout.write(self.style.SUCCESS(f"Reset link: {link}"))

        if do_send:
            try:
                sent = send_mail(
                    "Password Reset Request",
                    (
                        f"Hi {user.username},\n\n"
                        f"Click below to reset your password:\n{link}\n\n"
                        "If you didn’t request this, please ignore."
                    ),
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to send email: {e}"))
                return

            if sent:
                self.stdout.write(self.style.SUCCESS(f"Reset email sent to {email}"))
            else:
                self.stderr.write(self.style.ERROR("send_mail returned 0 — email not sent."))