import uuid
import pytest
from django.contrib.auth import get_user_model
from authentication.models import Organization, TeacherProfile
from authentication.permissions import IsTeacher, IsSchoolAdmin, IsSystemAdmin

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationModels:
    def test_create_organization(self):
        org = Organization.objects.create(
            name="1-sonli ixtisoslashtirilgan maktab",
            subscription_plan="pro",
            ai_monthly_token_budget=5_000_000
        )
        assert isinstance(org.id, uuid.UUID)
        assert org.name == "1-sonli ixtisoslashtirilgan maktab"
        assert org.subscription_plan == "pro"
        assert org.ai_monthly_token_budget == 5_000_000
        assert str(org) == "1-sonli ixtisoslashtirilgan maktab"

    def test_create_user_with_roles(self):
        org = Organization.objects.create(name="Prezident Maktabi")

        teacher = User.objects.create_user(
            username="sardor_teacher",
            email="sardor@example.com",
            password="SecurePassword123!",
            role="teacher",
            telegram_id=123456789,
            organization=org
        )
        assert isinstance(teacher.id, uuid.UUID)
        assert teacher.is_teacher is True
        assert teacher.is_school_admin is False
        assert teacher.is_system_admin is False
        assert teacher.organization == org
        assert teacher.telegram_id == 123456789

        admin_user = User.objects.create_user(
            username="botir_admin",
            email="botir@example.com",
            password="SecurePassword123!",
            role="school_admin",
            organization=org
        )
        assert admin_user.is_school_admin is True
        assert admin_user.is_teacher is False

        sys_admin = User.objects.create_superuser(
            username="super_admin",
            email="super@example.com",
            password="SuperPassword123!",
            role="system_admin"
        )
        assert sys_admin.is_system_admin is True

    def test_teacher_profile_creation(self):
        user = User.objects.create_user(
            username="malika_teacher",
            password="Password123!",
            role="teacher"
        )
        profile = TeacherProfile.objects.create(
            user=user,
            subject="Fizika",
            bio="7-sinf o'qituvchisi",
            phone_number="+998901234567"
        )
        assert isinstance(profile.id, uuid.UUID)
        assert profile.user == user
        assert user.teacher_profile == profile
        assert "malika_teacher" in str(profile)


@pytest.mark.django_db
class TestRBACPermissions:
    class DummyRequest:
        def __init__(self, user):
            self.user = user

    def test_is_teacher_permission(self):
        teacher = User.objects.create_user(username="t1", role="teacher")
        school_admin = User.objects.create_user(username="a1", role="school_admin")

        perm = IsTeacher()
        assert perm.has_permission(self.DummyRequest(teacher), None) is True
        assert perm.has_permission(self.DummyRequest(school_admin), None) is False

    def test_is_school_admin_permission(self):
        teacher = User.objects.create_user(username="t2", role="teacher")
        school_admin = User.objects.create_user(username="a2", role="school_admin")
        sys_admin = User.objects.create_user(username="s2", role="system_admin")

        perm = IsSchoolAdmin()
        assert perm.has_permission(self.DummyRequest(teacher), None) is False
        assert perm.has_permission(self.DummyRequest(school_admin), None) is True
        assert perm.has_permission(self.DummyRequest(sys_admin), None) is True

    def test_is_system_admin_permission(self):
        school_admin = User.objects.create_user(username="a3", role="school_admin")
        sys_admin = User.objects.create_user(username="s3", role="system_admin")

        perm = IsSystemAdmin()
        assert perm.has_permission(self.DummyRequest(school_admin), None) is False
        assert perm.has_permission(self.DummyRequest(sys_admin), None) is True
