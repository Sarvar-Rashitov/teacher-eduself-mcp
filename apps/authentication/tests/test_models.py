import uuid
import pytest
from django.db import IntegrityError
from apps.authentication.models import User, Organization, TeacherProfile


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_uuid(self):
        """User UUID primary key bilan yaratilishini tekshirish."""
        user = User.objects.create_user(
            username='test_teacher',
            email='teacher@example.com',
            password='strong_password_123',
            role='teacher'
        )
        assert isinstance(user.id, uuid.UUID)
        assert user.role == 'teacher'
        assert user.is_teacher is True
        assert user.is_school_admin is False
        assert user.is_system_admin is False

    def test_user_roles(self):
        """Har xil rollar to'g'ri tekshirilishini sinash."""
        school_admin = User.objects.create_user(
            username='admin_user',
            password='password123',
            role='school_admin'
        )
        assert school_admin.is_school_admin is True
        assert school_admin.is_teacher is False

        system_admin = User.objects.create_user(
            username='sys_admin',
            password='password123',
            role='system_admin'
        )
        assert system_admin.is_system_admin is True

    def test_telegram_id_uniqueness(self):
        """Bir xil telegram_id bilan ikkita foydalanuvchi ochilmasligini tekshirish."""
        User.objects.create_user(
            username='tg_user_1',
            password='password123',
            telegram_id=123456789
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                username='tg_user_2',
                password='password123',
                telegram_id=123456789
            )


@pytest.mark.django_db
class TestOrganizationModel:
    def test_create_organization(self):
        """Tashkilot yaratish va foydalanuvchiga biriktirish."""
        org = Organization.objects.create(
            name="1-sonli Ixtisoslashtirilgan Maktab",
            subscription_plan="school",
            ai_monthly_token_budget=5_000_000
        )
        assert isinstance(org.id, uuid.UUID)
        assert org.subscription_plan == "school"

        teacher = User.objects.create_user(
            username='org_teacher',
            password='password123',
            organization=org
        )
        assert teacher.organization == org
        assert org.members.count() == 1


@pytest.mark.django_db
class TestTeacherProfileModel:
    def test_create_teacher_profile(self):
        """TeacherProfile modeli to'g'ri ishlashi."""
        user = User.objects.create_user(username='prof_teacher', password='password123')
        profile = TeacherProfile.objects.create(
            user=user,
            subject="Fizika",
            bio="10 yillik tajribaga ega o'qituvchi",
            phone_number="+998901234567"
        )
        assert profile.user == user
        assert user.teacher_profile == profile
        assert profile.subject == "Fizika"
