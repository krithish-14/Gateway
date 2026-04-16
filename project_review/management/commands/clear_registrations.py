from django.core.management.base import BaseCommand
from project_review.models import Registration


class Command(BaseCommand):
    help = "Clear all startup registration records (and their registration numbers)."

    def handle(self, *args, **options):
        count = Registration.objects.count()
        Registration.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} registration record(s)."))