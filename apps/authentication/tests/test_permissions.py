"""
Unit tests for Role-Based Access Control (RBAC) permissions and view decorators.
"""

import pytest
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from apps.authentication.models import User
from apps.authentication.permissions import (
    teacher_required,
    school_admin_required,
    system_admin_required,
    IsTeacher,
    IsSchoolAdmin,
    IsSystemAdmin
)


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(username="teacher_user", role="teacher")


@pytest.fixture
def school_admin_user(db):
    return User.objects.create_user(username="admin_user", role="school_admin")


@pytest.fixture
def system_admin_user(db):
    return User.objects.create_user(username="sysadmin_user", role="system_admin")


def dummy_view(request):
    from django.http import JsonResponse
    return JsonResponse({'status': 'granted'})


def test_unauthenticated_request_rejected(rf):
    """Anonymous user must be rejected with 401."""
    request = rf.get('/some-view/')
    request.user = AnonymousUser()

    decorated = teacher_required(dummy_view)
    response = decorated(request)
    assert response.status_code == 401


def test_teacher_required_decorator(rf, teacher_user, school_admin_user):
    """teacher_required grants teacher and rejects non-teacher."""
    decorated = teacher_required(dummy_view)

    # Allowed for teacher
    req1 = rf.get('/')
    req1.user = teacher_user
    assert decorated(req1).status_code == 200

    # Denied for school_admin
    req2 = rf.get('/')
    req2.user = school_admin_user
    assert decorated(req2).status_code == 403


def test_school_admin_required_decorator(rf, teacher_user, school_admin_user, system_admin_user):
    """school_admin_required grants school_admin & system_admin, rejects teacher."""
    decorated = school_admin_required(dummy_view)

    # Denied for teacher
    req1 = rf.get('/')
    req1.user = teacher_user
    assert decorated(req1).status_code == 403

    # Allowed for school_admin
    req2 = rf.get('/')
    req2.user = school_admin_user
    assert decorated(req2).status_code == 200

    # Allowed for system_admin
    req3 = rf.get('/')
    req3.user = system_admin_user
    assert decorated(req3).status_code == 200


def test_drf_permission_classes(rf, teacher_user, school_admin_user, system_admin_user):
    """Verify DRF BasePermission classes."""
    is_teacher = IsTeacher()
    is_school_admin = IsSchoolAdmin()
    is_sys_admin = IsSystemAdmin()

    req = rf.get('/')
    req.user = teacher_user
    assert is_teacher.has_permission(req, None) is True
    assert is_school_admin.has_permission(req, None) is False
    assert is_sys_admin.has_permission(req, None) is False

    req.user = school_admin_user
    assert is_teacher.has_permission(req, None) is False
    assert is_school_admin.has_permission(req, None) is True
    assert is_sys_admin.has_permission(req, None) is False

    req.user = system_admin_user
    assert is_teacher.has_permission(req, None) is False
    assert is_school_admin.has_permission(req, None) is True
    assert is_sys_admin.has_permission(req, None) is True
