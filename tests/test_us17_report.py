from __future__ import annotations

import pytest
from app.database import Database
from app.models.report import Report
from app.models.notification import Notification
from app.repositories import ReportRepository


@pytest.fixture()
def setup_users(app, user_factory):
    with app.app_context():
        reporter = user_factory(email="reporter@example.com", full_name="Bob Reporter")
        target = user_factory(email="target@example.com", full_name="Alice Target")
        admin = user_factory(email="admin@example.com", full_name="Charlie Admin", role_name="admin")
        return {"reporter": reporter, "target": target, "admin": admin}


def test_anonymous_report_access(client, setup_users):
    # GET and POST should redirect to login
    res = client.get(f"/users/{setup_users['target'].id}/report")
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]

    res = client.post(f"/users/{setup_users['target'].id}/report", data={"reason": "spam"})
    assert res.status_code == 302
    assert "/auth/login" in res.headers["Location"]


def test_cannot_report_self(client, login, setup_users):
    login("reporter@example.com")
    res = client.post(
        f"/users/{setup_users['reporter'].id}/report",
        data={"reason": "spam", "description": "Reporting myself"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"You cannot report yourself" in res.data


def test_successful_reporting_and_notification(app, client, login, setup_users):
    login("reporter@example.com")
    res = client.post(
        f"/users/{setup_users['target'].id}/report",
        data={"reason": "harassment", "description": "Alice was mean."},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"submitted" in res.data.lower()

    # Verify DB state
    with app.app_context():
        reports = ReportRepository().list_all()
        assert len(reports) == 1
        r = reports[0]
        assert r.reporter_id == setup_users["reporter"].id
        assert r.reported_user_id == setup_users["target"].id
        assert r.reason == "harassment"
        assert r.description == "Alice was mean."
        assert r.status == "open"

        # Verify notification to reporter
        notifs = Notification.get_unread_notifications(setup_users["reporter"].id)
        assert len(notifs) == 1
        assert "received" in notifs[0].message.lower()
        assert "Alice Target" in notifs[0].message


def test_duplicate_reporting_restriction(app, client, login, setup_users):
    login("reporter@example.com")
    
    # First report
    client.post(
        f"/users/{setup_users['target'].id}/report",
        data={"reason": "spam"},
        follow_redirects=True,
    )
    
    # Second duplicate report immediately
    res = client.post(
        f"/users/{setup_users['target'].id}/report",
        data={"reason": "harassment"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"duplicate" in res.data.lower()

    with app.app_context():
        reports = ReportRepository().list_all()
        assert len(reports) == 1  # Only one report exists


def test_admin_reports_dashboard_and_resolution(app, client, login, setup_users):
    # 1. Non-admin gets 403
    login("reporter@example.com")
    res = client.get("/admin/reports")
    assert res.status_code == 403

    # Create a report directly
    with app.app_context():
        ReportRepository().create(
            reporter_id=setup_users["reporter"].id,
            reported_user_id=setup_users["target"].id,
            reason="fraud",
            description="Suspicious activity"
        )

    client.get("/auth/logout", follow_redirects=True)
    login("admin@example.com")

    # 2. Admin views dashboard
    res = client.get("/admin/reports")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Bob Reporter" in html
    assert "Alice Target" in html
    assert "Fraud" in html
    assert "Suspicious activity" in html

    # 3. Admin resolves report
    with app.app_context():
        reports = ReportRepository().list_all()
        r_id = reports[0].id
        
    res = client.post(f"/admin/reports/{r_id}/resolve?decision=resolved", follow_redirects=True)
    assert res.status_code == 200
    assert b"Report has been resolved" in res.data

    # Verify DB state
    with app.app_context():
        updated_r = ReportRepository().find_by_id(r_id)
        assert updated_r.status == "resolved"
        
        # Verify audit log
        db = Database()
        audit_log = db.fetch_one("SELECT * FROM admin_audit_logs WHERE action = 'resolve_report'")
        assert audit_log is not None
        assert audit_log["admin_id"] == setup_users["admin"].id
        assert "resolved" in audit_log["detail"]
        db.close()
