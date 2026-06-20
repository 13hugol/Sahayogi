from __future__ import annotations


def test_browse_catalog_lists_more_than_30_approved_skills_with_pagination(client):
    response = client.get("/listings/")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Explore 36 approved skill offers" in html
    assert "36</span> result(s)" in html
    assert "Python Automation Basics" in html
    assert "Candle Making For Gifts" not in html
    assert "Newest approved listings first, 20 per page" in html

    page_two = client.get("/listings/?page=2")
    assert page_two.status_code == 200
    assert "Candle Making For Gifts" in page_two.data.decode("utf-8")


def test_browse_search_supports_partial_keyword_matching(client):
    response = client.get("/listings/?q=guitarist")

    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Acoustic Guitar Fundamentals" in html
    assert "1</span> result(s)" in html
    assert "Keyword: guitarist" in html


def test_browse_api_filters_by_multiple_categories(client):
    response = client.get("/listings/api/search?category=1&category=2")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 18
    assert "Python Automation Basics" in payload["html"]
    assert "Acoustic Guitar Fundamentals" in payload["html"]
    assert "Newari Snack Workshop" not in payload["html"]


def test_saved_listing_session_flow(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "test-token"

    save_response = client.post(
        "/listings/1/save",
        data={"csrf_token": "test-token"},
        follow_redirects=True,
    )
    assert save_response.status_code == 200
    saved_html = save_response.data.decode("utf-8")
    assert "Saved listings" in saved_html
    assert "Python Automation Basics" in saved_html
    assert "Saved" in saved_html

    remove_response = client.post(
        "/listings/1/unsave",
        data={"csrf_token": "test-token"},
        follow_redirects=True,
    )
    assert remove_response.status_code == 200
    assert "0 bookmarked skill offer" in remove_response.data.decode("utf-8")
