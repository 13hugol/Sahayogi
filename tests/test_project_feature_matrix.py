from __future__ import annotations

from time import perf_counter


# Project feature matrix and performance smoke tests.
# These tests complement the user-story files by checking that the main feature
# surfaces are reachable and fast enough for a local student-project demo.


PUBLIC_FEATURE_ROUTES = (
    ("/", b"Sahayogi"),
    ("/auth/register", b"Create"),
    ("/auth/login", b"Log in"),
    ("/auth/forgot-password", b"password"),
    ("/listings/", b"skill"),
    ("/listings/categories", b"Categories"),
    ("/listings/api/search?q=python", b"count"),
    ("/reviews/top-rated", b"Top"),
)


AUTHENTICATED_FEATURE_ROUTES = (
    ("/dashboard", b"Dashboard"),
    ("/profile/me", b"Profile"),
    ("/profile/edit", b"Profile"),
    ("/profile/certificates", b"Certificate"),
    ("/listings/create", b"listing"),
    ("/listings/mine", b"listing"),
    ("/credits/ledger", b"Credit"),
    ("/matches/", b"Match"),
    ("/requests/inbox", b"Request"),
    ("/requests/sent", b"Request"),
    ("/exchanges/", b"Exchange"),
    ("/messages/", b"Messages"),
    ("/notifications/", b"Notifications"),
)


PROTECTED_FEATURE_ROUTES = tuple(route for route, _marker in AUTHENTICATED_FEATURE_ROUTES) + (
    "/admin/",
    "/admin/users",
    "/admin/listings",
    "/admin/certificates",
    "/admin/reports",
    "/admin/reviews",
    "/admin/categories",
    "/admin/skills",
)


def test_project_public_feature_routes_render(client):
    """AC-PROJ-1: Public discovery, auth, and trust pages render successfully."""
    for route, marker in PUBLIC_FEATURE_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert marker.lower() in response.data.lower(), route


def test_project_protected_routes_redirect_anonymous_users(client):
    """AC-PROJ-2: Private feature surfaces require login before access."""
    for route in PROTECTED_FEATURE_ROUTES:
        response = client.get(route)
        assert response.status_code == 302, route
        assert "/auth/login" in response.headers["Location"], route


def test_project_authenticated_feature_routes_render(app, client, login, user_factory):
    """AC-PROJ-3: Logged-in members can open the main user feature pages."""
    with app.app_context():
        user_factory(email="feature-member@example.com")

    login("feature-member@example.com")

    for route, marker in AUTHENTICATED_FEATURE_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert marker.lower() in response.data.lower(), route


def test_project_admin_feature_routes_are_role_gated(app, client, login, user_factory):
    """AC-PROJ-4: Admin tools reject members and render for administrators."""
    with app.app_context():
        user_factory(email="normal-member@example.com")
        user_factory(email="matrix-admin@example.com", role_name="admin")

    login("normal-member@example.com")
    member_response = client.get("/admin/")
    assert member_response.status_code == 403

    client.get("/auth/logout", follow_redirects=True)
    login("matrix-admin@example.com")

    admin_routes = (
        "/admin/",
        "/admin/users",
        "/admin/listings",
        "/admin/certificates",
        "/admin/reports",
        "/admin/reviews",
        "/admin/categories",
        "/admin/skills",
    )
    for route in admin_routes:
        response = client.get(route)
        assert response.status_code == 200, route


def test_project_public_pages_meet_demo_response_budget(client):
    """AC-PROJ-5: Core public pages stay responsive for local demonstration."""
    measured_routes = (
        "/",
        "/auth/login",
        "/listings/",
        "/listings/categories",
        "/listings/api/search?q=python",
    )
    timings = {}

    for route in measured_routes:
        started_at = perf_counter()
        response = client.get(route)
        timings[route] = perf_counter() - started_at
        assert response.status_code == 200, route

    assert max(timings.values()) < 2.0, timings
    assert sum(timings.values()) < 5.0, timings
