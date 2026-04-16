from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@test.local',
)
class RegistrationEmailTest(TestCase):
    def test_registration_sends_confirmation_email(self):
        url = reverse('project_review:startup_registration') + '?company=TCS'
        data = {
            'email': 'user@example.com',
            'company_name': 'TCS',
            'category': '',
            'team_size': '',
            'profile_text': '',
            'startup_name': 'Test Startup',
            'first_name': 'Test',
            'last_name': 'User',
            'file_type': '',
        }
        resp = self.client.post(url, data)
        self.assertIn(resp.status_code, (302, 200))
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn('user@example.com', mail.outbox[0].to)