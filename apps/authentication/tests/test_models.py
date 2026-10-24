import uuid
from django.test import TestCase
from apps.authentication.models import User, Organization


class UserModelTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="10-IDUM Maktabi",
            subscription_plan="pro",
            ai_monthly_token_budget=5_000_000,
        )

    def test_organization_creation(self):
        """Tashkilot to'g'ri yaratilishi va UUID primary key mavjudligi tekshiruvi."""
        self.assertIsInstance(self.org.id, uuid.UUID)
        self.assertEqual(str(self.org), "10-IDUM Maktabi")
        self.assertEqual(self.org.subscription_plan, "pro")
        self.assertEqual(self.org.ai_monthly_token_budget, 5_000_000)

    def test_user_creation_with_organization(self):
        """User yaratilishi, UUID va tashkilot bilan aloqasi tekshiruvi."""
        user = User.objects.create_user(
            username="teacher_alisher",
            email="alisher@example.com",
            password="SecurePassword123!",
            role="teacher",
            organization=self.org,
            telegram_id=987654321,
            preferred_locale="uz-Latn",
        )
        self.assertIsInstance(user.id, uuid.UUID)
        self.assertEqual(user.role, "teacher")
        self.assertTrue(user.is_teacher)
        self.assertFalse(user.is_school_admin)
        self.assertEqual(user.organization.name, "10-IDUM Maktabi")
        self.assertEqual(user.telegram_id, 987654321)

    def test_role_properties(self):
        """Foydalanuvchi rollari bo'yicha xususiyatlar tekshiruvi."""
        admin_user = User.objects.create_user(
            username="admin_user",
            email="admin@example.com",
            password="SecurePassword123!",
            role="school_admin",
            organization=self.org,
        )
        self.assertFalse(admin_user.is_teacher)
        self.assertTrue(admin_user.is_school_admin)
        self.assertFalse(admin_user.is_system_admin)

        sys_admin = User.objects.create_user(
            username="sys_admin",
            email="sysadmin@example.com",
            password="SecurePassword123!",
            role="system_admin",
        )
        self.assertTrue(sys_admin.is_school_admin)
        self.assertTrue(sys_admin.is_system_admin)
