from __future__ import annotations

from app.extensions import db
from app.models import Listing, Skill, User, Review, AdminAuditLog, Report, Exchange, ExchangeRequest


def test_admin_can_approve_listing(app, client, login, user_factory):
    with app.app_context():
        admin = user_factory(email="admin@example.com", full_name="Admin User", role_name="admin")
        member = user_factory(email="member@example.com", full_name="Member User")
        skill = Skill.query.filter_by(name="SQL").first()
        listing = Listing(
            user=member,
            skill=skill,
            category=skill.category,
            title="SQL tutoring",
            description="Hands-on SQL support covering joins, filters, and schema reading.",
            exchange_type="teach",
            status="pending",
        )
        db.session.add(listing)
        db.session.commit()
        listing_id = listing.id

    login("admin@example.com")
    response = client.post(f"/admin/listings/{listing_id}/approve", follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        listing = db.session.get(Listing, listing_id)
        assert listing.status == "approved"
        assert listing.approved_at is not None


def test_admin_access_control(app, client, login, user_factory):
    # Unauthenticated redirect to login
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]

    # Regular user gets 403
    with app.app_context():
        user_factory(email="user@example.com", role_name="user")
    login("user@example.com")
    
    for url in ["/admin/", "/admin/users", "/admin/listings", "/admin/reports", "/admin/reviews"]:
        response = client.get(url)
        assert response.status_code == 403

    # Logout the regular user session
    client.get("/auth/logout", follow_redirects=True)

    # Admin user gets 200
    with app.app_context():
        user_factory(email="admin2@example.com", role_name="admin")
    login("admin2@example.com")
    
    for url in ["/admin/", "/admin/users", "/admin/listings", "/admin/reports", "/admin/reviews"]:
        response = client.get(url)
        assert response.status_code == 200


def test_admin_dashboard_metrics(app, client, login, user_factory):
    with app.app_context():
        # Setup data
        admin = user_factory(email="admin_metrics@example.com", role_name="admin")
        member1 = user_factory(email="m1_metrics@example.com")
        member2 = user_factory(email="m2_metrics@example.com")
        
        # Create an approved listing
        skill = Skill.query.first()
        listing_approved = Listing(
            user=member1,
            skill=skill,
            category=skill.category,
            title="Approved listing",
            description="Short desc",
            exchange_type="teach",
            status="approved",
        )
        # Create a pending listing
        listing_pending = Listing(
            user=member2,
            skill=skill,
            category=skill.category,
            title="Pending listing",
            description="Short desc",
            exchange_type="teach",
            status="pending",
        )
        db.session.add(listing_approved)
        db.session.add(listing_pending)
        
        # Create an open report
        report = Report(
            reporter=member1,
            reported_user=member2,
            reason="harassment",
            description="Abuse",
            status="open",
        )
        db.session.add(report)
        
        # Create an exchange
        req = ExchangeRequest(
            listing=listing_approved,
            sender=member2,
            recipient=member1,
            request_type="teach",
            status="accepted",
        )
        db.session.add(req)
        db.session.flush()
        
        exchange = Exchange(
            request=req,
            listing=listing_approved,
            teacher=member1,
            learner=member2,
            exchange_type="teach",
            status="active",
        )
        db.session.add(exchange)
        db.session.commit()

    login("admin_metrics@example.com")
    response = client.get("/admin/")
    assert response.status_code == 200
    
    # Verify exact metrics are present in response text
    content = response.data.decode("utf-8")
    assert "Total users" in content
    assert "Active listings" in content
    assert "Pending approvals" in content
    assert "Open reports" in content
    assert "Daily exchanges" in content


def test_admin_review_moderation(app, client, login, user_factory):
    with app.app_context():
        admin = user_factory(email="admin_moderation@example.com", role_name="admin")
        member1 = user_factory(email="m1_mod@example.com")
        member2 = user_factory(email="m2_mod@example.com")
        admin_id = admin.id
        
        # We need an exchange to write a review
        skill = Skill.query.first()
        listing = Listing(
            user=member1,
            skill=skill,
            category=skill.category,
            title="Tutoring",
            description="Desc desc",
            exchange_type="teach",
            status="approved",
        )
        db.session.add(listing)
        db.session.flush()
        
        req = ExchangeRequest(
            listing=listing,
            sender=member2,
            recipient=member1,
            request_type="teach",
            status="accepted",
        )
        db.session.add(req)
        db.session.flush()
        
        exchange = Exchange(
            request=req,
            listing=listing,
            teacher=member1,
            learner=member2,
            exchange_type="teach",
            status="completed",
        )
        db.session.add(exchange)
        db.session.flush()
        
        # Write a review from member2 to member1
        review = Review(
            exchange=exchange,
            reviewer=member2,
            reviewee=member1,
            rating=5,
            comment="Excellent class!",
        )
        db.session.add(review)
        db.session.commit()
        
        review_id = review.id
        member1_id = member1.id

    # Verify reviewee reputation score updated
    with app.app_context():
        from app.services import recalculate_reputation
        m1 = db.session.get(User, member1_id)
        recalculate_reputation(m1)
        db.session.commit()
        assert m1.profile.reputation_score == 5.0
        assert m1.profile.review_count == 1

    # Login as admin and reject review
    login("admin_moderation@example.com")
    
    # View reviews moderation page
    response = client.get("/admin/reviews")
    assert response.status_code == 200
    assert "Excellent class!" in response.data.decode("utf-8")
    
    # Reject the review
    response = client.post(f"/admin/reviews/{review_id}/reject", follow_redirects=True)
    assert response.status_code == 200
    assert "Review rejected and deleted" in response.data.decode("utf-8")
    
    with app.app_context():
        # Verify review is deleted
        assert db.session.get(Review, review_id) is None
        
        # Verify reputation score recalculated to 0.0
        m1 = db.session.get(User, member1_id)
        assert m1.profile.reputation_score == 0.0
        assert m1.profile.review_count == 0
        
        # Verify audit log was created
        audit_log = AdminAuditLog.query.filter_by(action="reject_review").first()
        assert audit_log is not None
        assert audit_log.admin_id == admin_id
        assert audit_log.target_type == "Review"
        assert audit_log.target_id == review_id
        assert "Rejected review" in audit_log.detail
        assert audit_log.created_at is not None


def test_admin_update_user_role(app, client, login, user_factory):
    with app.app_context():
        admin = user_factory(email="admin_role@example.com", role_name="admin")
        member = user_factory(email="member_role@example.com")
        member_id = member.id
    
    # Non-admin user cannot elevate role
    login("member_role@example.com")
    response = client.post(f"/admin/users/{member_id}/role", data={"role-role": "admin"})
    assert response.status_code == 403

    client.get("/auth/logout", follow_redirects=True)

    # Admin can update role
    login("admin_role@example.com")
    response = client.post(
        f"/admin/users/{member_id}/role", 
        data={"role-role": "admin"}, 
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "role updated to &#39;admin&#39;" in response.data.decode("utf-8") or "role updated to 'admin'" in response.data.decode("utf-8")

    with app.app_context():
        updated_user = db.session.get(User, member_id)
        assert updated_user.role.name == "admin"
        
        # Verify audit log
        audit_log = AdminAuditLog.query.filter_by(action="update_user_role").first()
        assert audit_log is not None
        assert "Role changed" in audit_log.detail
