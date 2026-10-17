import pytest
from unittest.mock import Mock
from django.contrib.auth.models import AnonymousUser
from apps.authentication.models import User
from apps.authentication.permissions import (
    IsTeacher,
    IsSchoolAdmin,
    IsSystemAdmin,
    HasRole,
    IsSelfOrAdmin
)


def make_request(user=None):
    request = Mock()
    request.user = user if user is not None else AnonymousUser()
    return request


@pytest.mark.django_db
class TestRBACPermissions:
    def test_is_teacher_permission(self):
        teacher = User(username='t1', role='teacher')
        school_admin = User(username='a1', role='school_admin')
        anonymous = AnonymousUser()

        perm = IsTeacher()
        assert perm.has_permission(make_request(teacher), None) is True
        assert perm.has_permission(make_request(school_admin), None) is False
        assert perm.has_permission(make_request(anonymous), None) is False

    def test_is_school_admin_permission(self):
        teacher = User(username='t2', role='teacher')
        school_admin = User(username='a2', role='school_admin')
        system_admin = User(username='s2', role='system_admin')

        perm = IsSchoolAdmin()
        assert perm.has_permission(make_request(school_admin), None) is True
        assert perm.has_permission(make_request(system_admin), None) is True
        assert perm.has_permission(make_request(teacher), None) is False

    def test_is_system_admin_permission(self):
        teacher = User(username='t3', role='teacher')
        school_admin = User(username='a3', role='school_admin')
        system_admin = User(username='s3', role='system_admin')

        perm = IsSystemAdmin()
        assert perm.has_permission(make_request(system_admin), None) is True
        assert perm.has_permission(make_request(teacher), None) is False
        assert perm.has_permission(make_request(school_admin), None) is False

    def test_has_role_helper(self):
        teacher = User(username='t4', role='teacher')
        school_admin = User(username='a4', role='school_admin')

        perm_cls = HasRole.with_roles('teacher')
        perm = perm_cls()
        assert perm.has_permission(make_request(teacher), None) is True
        assert perm.has_permission(make_request(school_admin), None) is False

    def test_is_self_or_admin(self):
        user1 = User(username='u1', role='teacher', is_superuser=False)
        user2 = User(username='u2', role='teacher', is_superuser=False)
        admin = User(username='admin', role='system_admin', is_superuser=True)

        perm = IsSelfOrAdmin()
        assert perm.has_object_permission(make_request(user1), None, user1) is True
        assert perm.has_object_permission(make_request(user1), None, user2) is False
        assert perm.has_object_permission(make_request(admin), None, user2) is True
