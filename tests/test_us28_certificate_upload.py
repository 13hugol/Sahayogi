from __future__ import annotations

import io
import pytest
from app.models import AdminAuditLog
from app.models.profile import ProfileSkill, ProfileCertificate
from app.models.skill import Skill, Category
from app.repositories import SkillRepository, CategoryRepository, ProfileCertificateRepository
from app.enums import SkillType, CertificateStatus


@pytest.fixture()
def seed_categories(app):
    with app.app_context():
        cat_repo = CategoryRepository()
        tech = cat_repo.ensure("Tech", "Tech skills")
        music = cat_repo.ensure("Music", "Music skills")
        return {
            "Tech": tech,
            "Music": music,
        }


def test_certificate_upload_validation_failures(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        tech_cat_id = seed_categories["Tech"].id

    login("alice@example.com")

    # 1. Invalid extension (e.g. txt)
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm",
        "certificate": (io.BytesIO(b"fake txt contents"), "cert.txt")
    }, content_type="multipart/form-data", follow_redirects=True)

    html = res.data.decode("utf-8")
    assert "Certificate must be a PDF, JPG, or PNG file." in html

    # 2. Too large (>10MB)
    large_data = b"0" * (10 * 1024 * 1024 + 100) # > 10MB
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm",
        "certificate": (io.BytesIO(large_data), "cert.pdf")
    }, content_type="multipart/form-data", follow_redirects=True)

    html = res.data.decode("utf-8")
    assert "Certificate must be under 10MB." in html

    # 3. Invalid header for PDF
    res = client.post("/listings/create", data={
        "title": "Valid Python mentor offer",
        "description": "Let us learn Python together with step-by-step guides.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat_id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app message",
        "availability_labels": "Weekends 9am-12pm",
        "certificate": (io.BytesIO(b"not a pdf header contents"), "cert.pdf")
    }, content_type="multipart/form-data", follow_redirects=True)

    html = res.data.decode("utf-8")
    assert "Certificate file content must match the PDF format." in html


def test_certificate_upload_success_and_admin_flow(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        admin = user_factory(email="admin@example.com", role_name="admin")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        tech_cat = seed_categories["Tech"]

    login("alice@example.com")

    # Post listing with a valid PDF certificate
    res = client.post("/listings/create", data={
        "title": "Learn Python step by step",
        "description": "I will teach you the fundamentals of Python programming.",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat.id),
        "min_credits": "15",
        "location_text": "Kathmandu",
        "contact_method": "In-app messaging",
        "availability_labels": "Weekends only",
        "certificate": (io.BytesIO(b"%PDF-1.4 test certificate"), "cert.pdf")
    }, content_type="multipart/form-data", follow_redirects=True)

    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Listing submitted successfully and is pending admin review." in html

    # Verify listing and certificate state in DB
    with app.app_context():
        listings = Skill.find_by_user_id(user.id)
        assert len(listings) == 1
        listing = listings[0]
        assert listing.certificate_path is not None
        assert listing.certificate_status == "pending"

        # Check profile_certificates entry
        cert_repo = ProfileCertificateRepository()
        certs = cert_repo.find_by_user_id(user.id)
        assert len(certs) == 1
        cert = certs[0]
        assert cert.status == "pending"
        assert cert.profile_skill_id == ps1.id
        assert cert.file_path == listing.certificate_path

    # Check listing detail page shows Verification Pending badge
    res = client.get(f"/listings/{listing.id}")
    assert "Verification Pending" in res.data.decode("utf-8")

    # Log in as admin and view review queue
    client.get("/auth/logout", follow_redirects=True)
    login("admin@example.com")

    res = client.get("/admin/certificates")
    assert res.status_code == 200
    admin_html = res.data.decode("utf-8")
    assert "Alice" in admin_html or "Test Member" in admin_html
    assert "Python coding" in admin_html

    # Approve certificate
    res = client.post(f"/admin/certificates/{cert.id}/approve", data={
        "notes": "Verified official certificate."
    }, follow_redirects=True)

    assert res.status_code == 200
    assert "approved successfully" in res.data.decode("utf-8").lower()

    # Verify approved state in DB
    with app.app_context():
        listing = Skill.find_by_id(listing.id)
        assert listing.certificate_status == "approved"

        # profile skill check
        skills = ProfileSkill.find_for_user(user.id, SkillType.OFFERED)
        assert len(skills) == 1
        assert skills[0].has_verified_certificate is True

        # audit log check
        log = AdminAuditLog.find_by_action("approve_certificate")
        assert log is not None
        assert log.target_id == cert.id

    # Check listing detail page shows Verified skill badge
    client.get("/auth/logout", follow_redirects=True)
    login("alice@example.com")
    res = client.get(f"/listings/{listing.id}")
    assert "Verified skill" in res.data.decode("utf-8")


def test_certificate_edit_and_removal(app, client, login, user_factory, seed_categories):
    with app.app_context():
        user = user_factory(email="alice@example.com")
        ps1 = ProfileSkill.create(user.id, "Python coding", SkillType.OFFERED)
        tech_cat = seed_categories["Tech"]

        # Create listing with approved certificate directly in DB
        from app.database import Database
        db = Database()
        listing_id = db.execute(
            """
            INSERT INTO skills (user_id, category_id, skill_id, title, description, availability, status, certificate_path, certificate_status)
            VALUES (%s, %s, %s, 'Title', 'Description longer than ten', 'Daily', 'approved', 'certificates/cert1.pdf', 'approved')
            """,
            (user.id, tech_cat.id, ps1.id)
        )
        db.execute(
            """
            INSERT INTO profile_certificates (user_id, profile_skill_id, skill_name, status, file_path)
            VALUES (%s, %s, 'Python coding', 'approved', 'certificates/cert1.pdf')
            """,
            (user.id, ps1.id)
        )

    login("alice@example.com")

    # Remove certificate on edit form
    res = client.post(f"/listings/{listing_id}/edit", data={
        "title": "Title - Updated",
        "description": "Description longer than ten - Updated",
        "exchange_type": "credit",
        "skill_id": str(ps1.id),
        "category_id": str(tech_cat.id),
        "min_credits": "10",
        "location_text": "Kathmandu",
        "contact_method": "In-app messaging",
        "availability_labels": "Weekends only",
        "remove_certificate": "on"
    }, follow_redirects=True)

    assert res.status_code == 200
    assert "updated successfully" in res.data.decode("utf-8").lower()

    # Verify reset/removed state in DB
    with app.app_context():
        listing = Skill.find_by_id(listing_id)
        assert listing.certificate_path is None
        assert listing.certificate_status == "none"

        # Check profile skill doesn't have verified flag
        skills = ProfileSkill.find_for_user(user.id, SkillType.OFFERED)
        assert len(skills) == 1
        assert skills[0].has_verified_certificate is False

        # profile_certificates entry deleted or none
        cert_repo = ProfileCertificateRepository()
        certs = cert_repo.find_by_user_id(user.id)
        assert len(certs) == 0
