import pytest
from fastapi import HTTPException
from app.models.user import User, RoleType
from app.core.dependencies import get_current_admin
from app.models.audit import AdminAuditLog

def test_user_role_defaults_to_user():
    user = User(first_name="Test", last_name="User", email="test@test.com", hashed_password="pw")
    # role defaults to USER (handled by DB default, but SQLAlchemy python default is also set)
    assert user.role == RoleType.USER

def test_get_current_admin_success():
    admin = User(id=1, email="admin@bazzix.com", role=RoleType.ADMIN)
    result = get_current_admin(user=admin)
    assert result == admin

def test_get_current_admin_rejects_normal_user():
    normal_user = User(id=2, email="user@bazzix.com", role=RoleType.USER)
    with pytest.raises(HTTPException) as exc_info:
        get_current_admin(user=normal_user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Insufficient permissions"

def test_admin_audit_log_instantiation():
    log = AdminAuditLog(admin_user_id=1, target_user_id=2, target_user_email="test@test.com", action="GRANT_CREDITS", details={"amount": 100})
    assert log.admin_user_id == 1
    assert log.target_user_id == 2
    assert log.target_user_email == "test@test.com"
    assert log.action == "GRANT_CREDITS"
    assert log.details == {"amount": 100}

