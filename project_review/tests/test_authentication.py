from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core import mail
from django.contrib.messages import get_messages
from project_review.views import reset_tokens
import json


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@test.local',
)
class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_view_get(self):
        """Test login page loads correctly"""
        response = self.client.get(reverse('project_review:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'project_review/login.html')

    def test_login_view_post_valid_credentials(self):
        """Test successful login redirects to home"""
        response = self.client.post(reverse('project_review:login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertRedirects(response, reverse('project_review:home'))

    def test_login_view_post_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(reverse('project_review:login'), {
            'username': 'testuser',
            'password': 'wrongpass'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'project_review/login.html')
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Invalid username/email or password' in str(msg) for msg in messages))

    def test_login_view_post_email_login(self):
        """Test login using email instead of username"""
        response = self.client.post(reverse('project_review:login'), {
            'username': 'test@example.com',
            'password': 'testpass123'
        })
        self.assertRedirects(response, reverse('project_review:home'))

    def test_forgot_password_view_get(self):
        """Test forgot password page loads"""
        response = self.client.get(reverse('project_review:forgot_password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'project_review/forgot_password.html')

    def test_forgot_password_view_post_valid_email(self):
        """Test forgot password with valid email redirects back"""
        response = self.client.post(reverse('project_review:forgot_password'), {
            'email': 'test@example.com'
        })
        # View redirects back to forgot_password after POST
        self.assertRedirects(response, reverse('project_review:forgot_password'))

    def test_forgot_password_view_post_invalid_email(self):
        """Test forgot password with invalid email redirects back"""
        response = self.client.post(reverse('project_review:forgot_password'), {
            'email': 'nonexistent@example.com'
        })
        self.assertRedirects(response, reverse('project_review:forgot_password'))

    def test_reset_password_view_get_invalid_token(self):
        """Test reset password with invalid token redirects to forgot_password"""
        response = self.client.get(reverse('project_review:reset_password', args=['invalidtoken']))
        self.assertRedirects(response, reverse('project_review:forgot_password'))

    def test_reset_password_view_get_valid_token(self):
        """Test reset password page loads with valid DB token"""
        from project_review.models import PasswordResetToken
        prt = PasswordResetToken.objects.create(user=self.user, token='validtoken123')
        response = self.client.get(reverse('project_review:reset_password', args=['validtoken123']))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'project_review/reset_password.html')

    def test_reset_password_view_post_valid_token(self):
        """Test password reset with valid DB token"""
        from project_review.models import PasswordResetToken
        PasswordResetToken.objects.create(user=self.user, token='validtoken456')
        response = self.client.post(reverse('project_review:reset_password', args=['validtoken456']), {
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertRedirects(response, reverse('project_review:login'))
        # Verify password was changed
        user = User.objects.get(username='testuser')
        self.assertTrue(user.check_password('newpassword123'))

    def test_reset_password_view_post_password_mismatch(self):
        """Test password reset with mismatched passwords"""
        from project_review.models import PasswordResetToken
        PasswordResetToken.objects.create(user=self.user, token='validtoken789')
        response = self.client.post(reverse('project_review:reset_password', args=['validtoken789']), {
            'password': 'newpassword123',
            'confirm_password': 'differentpassword'
        })
        # Redirects back to same page on mismatch
        self.assertEqual(response.status_code, 302)

    def test_home_view_authenticated(self):
        """Test home access when authenticated"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('project_review:home'))
        self.assertEqual(response.status_code, 200)

    def test_home_view_unauthenticated(self):
        """Test home redirect when not authenticated"""
        response = self.client.get(reverse('project_review:home'))
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])


class URLTests(TestCase):
    def test_urls_resolve_correctly(self):
        """Test that all URLs resolve to correct views"""
        from project_review.urls import urlpatterns
        from django.urls import resolve

        # Test login URL
        match = resolve('/login/')
        self.assertEqual(match.url_name, 'login')

        # Test forgot password URL
        match = resolve('/forgot-password/')
        self.assertEqual(match.url_name, 'forgot_password')

        # Test home URL
        match = resolve('/home/')
        self.assertEqual(match.url_name, 'home')


class TemplateTests(TestCase):
    def test_templates_exist_and_render(self):
        """Test that templates exist and render without errors"""
        client = Client()

        # Test login template
        response = client.get(reverse('project_review:login'))
        self.assertContains(response, 'Login')

        # Test forgot password template
        response = client.get(reverse('project_review:forgot_password'))
        self.assertContains(response, 'Forgot Password')


class SecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_reset_token_used_after_reset(self):
        """Test that reset tokens are marked as used after password reset"""
        from project_review.models import PasswordResetToken
        prt = PasswordResetToken.objects.create(user=self.user, token='sectoken123')

        # Use the token
        self.client.post(reverse('project_review:reset_password', args=['sectoken123']), {
            'password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })

        # Token should be marked as used
        prt.refresh_from_db()
        self.assertTrue(prt.used)

    def test_sql_injection_prevention(self):
        """Test that login is safe from SQL injection"""
        response = self.client.post(reverse('project_review:login'), {
            'username': "' OR '1'='1",
            'password': 'anything'
        })
        self.assertEqual(response.status_code, 200)
        # Should not log in
        self.assertNotIn('_auth_user_id', self.client.session)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='noreply@test.local',
)
class EmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_reset_email_sent_on_forgot_password(self):
        """Test that reset email is sent when forgot password is submitted"""
        client = Client()
        client.post(reverse('project_review:forgot_password'), {
            'email': 'test@example.com'
        })

        # Check email content
        self.assertGreaterEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('testuser', email.body)
        self.assertEqual(email.to, ['test@example.com'])
