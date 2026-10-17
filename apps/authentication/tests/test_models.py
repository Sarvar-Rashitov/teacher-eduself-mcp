"""
Unit tests for User, Organization, and TeacherProfile models.
"""

import uuid
import pytest
from apps.authentication.models import User, Organization, TeacherProfile


@pytest.mark.django_db
def test_organization_creation_defaults():
    """Verify Organization model creation and default values."""
    org = Organization.objects.create(name="Toshkent 17-maktab")
    assert isinstance(org.id, uuid.UUID)
    assert org.subscription_plan == 'free'
    assert org.ai_monthly_token_budget == 1_000_000
    assert str(org) == "Toshkent 17-maktab"


@pytest.mark.django_db
def test_user_creation_with_uuid_and_roles():
    """Verify custom User model properties and role methods."""
    user = User.objects.create_user(
        username="teacher_alisher",
        email="alisher@maktab.uz",
        password="ValidStrongPassword123!",
        role="teacher",
        telegram_id=987654321,
        preferred_locale="uz-Latn"
    )

    assert isinstance(user.id, uuid.UUID)
    assert user.role == 'teacher'
    assert user.is_teacher() is True
    assert user.is_school_admin() is False
    assert user.is_system_admin() is False
    assert user.telegram_id == 987654321
    assert user.preferred_locale == "uz-Latn"


@pytest.mark.django_db
def test_school_admin_and_system_admin_roles():
    """Verify school admin and system admin role helpers."""
    school_admin = User.objects.create_user(
        username="admin_maktab",
        role="school_admin"
    )
    assert school_admin.is_teacher() is False
    assert school_admin.is_school_admin() is True
    assert school_admin.is_system_admin() is False

    system_admin = User.objects.create_user(
        username="sysadmin",
        role="system_admin"
    )
    assert system_admin.is_system_admin() is True


@pytest.mark.django_db
def test_teacher_profile_one_to_one():
    """Verify TeacherProfile creation linked to User."""
    teacher = User.objects.create_user(
        username="sardor_aka",
        first_name="Sardor",
        last_name="Rasulov",
        role="teacher"
    )
    profile = TeacherProfile.objects.create(
        user=teacher,
        subject_specialization="Fizika",
        default_grade=8,
        school_name="Prezident Maktabi"
    )

    assert teacher.teacher_profile == profile
    assert profile.subject_specialization == "Fizika"
    assert profile.default_grade == 8
    assert "Sardor Rasulov profili" in str(profile)


@pytest.mark.django_db
def test_organization_membership_relation():
    """Verify User to Organization relationship."""
    org = Organization.objects.create(name="Samarqand Litseyi")
    user = User.objects.create_user(
        username="litsey_teacher",
        organization=org,
        role="teacher"
    )
    assert user.organization == org
    assert user in org.members.all()
