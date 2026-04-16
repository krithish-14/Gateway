from django.core.management.base import BaseCommand
from project_review.utils.email import send_transactional_email

class Command(BaseCommand):
    help = 'Send a test email via configured SMTP.'

    def add_arguments(self, parser):
        parser.add_argument('to_email')

    def handle(self, *args, **options):
        to_email = options['to_email']
        sent = send_transactional_email(
            to_email,
            'Test Email',
            'This is a test email.',
            '<p>This is a test email.</p>',
        )
        if sent:
            self.stdout.write('Email sent')
        else:
            self.stdout.write('Email not sent')
