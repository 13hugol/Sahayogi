from __future__ import annotations

from app.models import AdminAuditLog, User


def test_admin_access_control(app, client, login, user_factory):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]

    with app.app_context():
        user_factory(email="user@example.com", role_name="user")
    login("user@example.com")

    for url in ["/admin/", "/admin/users"]:
        response = client.get(url)
        assert response.status_code == 403

    client.get("/auth/logout", follow_redirects=True)

    with app.app_context():
        user_factory(email="admin@example.com", role_name="admin")
    login("admin@example.com")

    for url in ["/admin/", "/admin/users"]:
        response = client.get(url)
        assert response.status_code == 200


def test_admin_dashboard_metrics(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="admin_metrics@example.com", role_name="admin", verified=True)
        user_factory(email="member_metrics@example.com", role_name="user", verified=False)

    login("admin_metrics@example.com")
    response = client.get("/admin/")
    assert response.status_code == 200

    content = response.data.decode("utf-8")
    assert "Total users" in content
    assert "Admin users" in content
    assert "Regular users" in content
    assert "Verified users" in content


def test_admin_update_user_role(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="admin_role@example.com", role_name="admin")
        member = user_factory(email="member_role@example.com")
        member_id = member.id

    login("member_role@example.com")
    response = client.post(f"/admin/users/{member_id}/role", data={"role": "admin"})
    assert response.status_code == 403

    client.get("/auth/logout", follow_redirects=True)

    login("admin_role@example.com")
    response = client.post(
        f"/admin/users/{member_id}/role",
        data={"role": "admin"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "role updated" in response.data.decode("utf-8")

    with app.app_context():
        updated_user = User.find_by_id(member_id)
        assert updated_user.role.name == "admin"

        audit_log = AdminAuditLog.find_by_action("update_user_role")
        assert audit_log is not None
        assert "Role changed" in audit_log.detail
