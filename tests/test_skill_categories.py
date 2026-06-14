from __future__ import annotations

from app.models import AdminAuditLog
from app.repositories import CategoryRepository


def test_category_overview_lists_required_categories_with_active_counts(client):
    response = client.get("/listings/categories")

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    for name in ("Tech", "Music", "Language", "Kitchen"):
        assert name in content
    for label in ("TECH", "MUS", "LANG", "KIT"):
        assert label in content
    assert content.count("9 active") == 4


def test_create_listing_form_uses_one_required_primary_category(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="category_member@example.com")

    login("category_member@example.com")
    response = client.get("/listings/create")

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert 'name="category_id"' in content
    assert 'name="category_id" class="form-select" required' in content
    assert 'name="category_id" class="form-select" required multiple' not in content
    assert "Choose one category" in content
    assert "TECH - Tech" in content


def test_admin_can_create_category_without_code_deployment(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="category_admin@example.com", role_name="admin")

    login("category_admin@example.com")
    response = client.post(
        "/admin/categories",
        data={
            "name": "Art Craft",
            "slug": "",
            "icon": "ART",
            "description": "Hands-on drawing, making, and practical art sessions.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Category Art Craft created." in content
    assert "Art Craft" in content
    assert "art-craft" in content
    assert "ART" in content

    overview = client.get("/listings/categories").data.decode("utf-8")
    assert "Art Craft" in overview
    assert "0 active" in overview

    listing_form = client.get("/listings/create").data.decode("utf-8")
    assert "ART - Art Craft" in listing_form

    with app.app_context():
        category = next(item for item in CategoryRepository().all() if item.slug == "art-craft")
        assert category.name == "Art Craft"
        audit_log = AdminAuditLog.find_by_action("create_category")
        assert audit_log is not None
        assert audit_log.target_id == category.id


def test_admin_can_rename_category_and_listing_cards_use_new_label(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="rename_category_admin@example.com", role_name="admin")

    login("rename_category_admin@example.com")
    response = client.post(
        "/admin/categories/1/edit",
        data={
            "name": "Technology",
            "slug": "technology",
            "icon": "TECHX",
            "description": "Programming and digital productivity sessions.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Category Technology updated." in response.data.decode("utf-8")

    marketplace = client.get("/listings/").data.decode("utf-8")
    assert "Technology" in marketplace
    assert "TECHX" in marketplace
    assert "Python Automation Basics" in marketplace

    with app.app_context():
        category = CategoryRepository().find_by_id(1)
        assert category.name == "Technology"
        audit_log = AdminAuditLog.find_by_action("rename_category")
        assert audit_log is not None
        assert audit_log.target_id == 1


def test_duplicate_category_name_shows_inline_error(app, client, login, user_factory):
    with app.app_context():
        user_factory(email="duplicate_category_admin@example.com", role_name="admin")

    login("duplicate_category_admin@example.com")
    response = client.post(
        "/admin/categories",
        data={
            "name": "Tech",
            "slug": "tech-copy",
            "icon": "TC",
            "description": "Duplicate category attempt.",
        },
    )

    assert response.status_code == 200
    assert "A category with this name already exists." in response.data.decode("utf-8")
