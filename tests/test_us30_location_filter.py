import pytest
from app.database import Database
from app.repositories import ProfileRepository, SkillRepository
from app.utils.distance import haversine_distance

def test_haversine_distance_calculation():
    # AC-4: Haversine outputs correct distance (Kathmandu to Pokhara ~ 143km)
    ktm = (27.7172, 85.3240)
    pkr = (28.2096, 83.9856)
    dist = haversine_distance(ktm, pkr)
    assert 140 < dist < 150

def test_profile_repository_save_location(app, user_factory):
    with app.app_context():
        user = user_factory()
        profile_repo = ProfileRepository()
        profile_repo.save_location_coords(user.id, 27.7172, 85.3240, "Kathmandu")
        
        profile = profile_repo.find_by_user_id(user.id)
        assert profile.latitude == 27.7172
        assert profile.longitude == 85.3240
        assert profile.location_label == "Kathmandu"

def test_skill_repository_search_by_location(app, user_factory):
    with app.app_context():
        db = Database()
        cat_id = db.execute("INSERT INTO categories (name, description) VALUES ('Tech', 'Tech')")
        
        u1 = user_factory(email="u1@test.com", location="KTM")
        u2 = user_factory(email="u2@test.com", location="PKR")
        
        profile_repo = ProfileRepository()
        profile_repo.save_location_coords(u1.id, 27.7172, 85.3240, "Kathmandu")
        profile_repo.save_location_coords(u2.id, 28.2096, 83.9856, "Pokhara")
        
        ps1 = db.execute("INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, %s)", (u1.id, "Python", "offered"))
        ps2 = db.execute("INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, %s)", (u2.id, "Java", "offered"))
        
        skill_repo = SkillRepository()
        skill_repo.create(
            user_id=u1.id, category_id=cat_id, skill_id=ps1, title="Python", description="Python", 
            exchange_type="free", credit_cost=0, availability="any", status="approved"
        )
        skill_repo.create(
            user_id=u2.id, category_id=cat_id, skill_id=ps2, title="Java", description="Java", 
            exchange_type="free", credit_cost=0, availability="any", status="approved"
        )
        
        # Search within 10km of Kathmandu
        res1 = skill_repo.search_by_location(27.7172, 85.3240, 10, status="approved")
        assert len(res1) == 1
        assert res1[0].user_id == u1.id
        assert res1[0].distance == 0.0
        
        # Search within 200km of Kathmandu (should include Pokhara)
        res2 = skill_repo.search_by_location(27.7172, 85.3240, 200, status="approved")
        assert len(res2) == 2
        assert res2[0].user_id == u1.id
        assert res2[1].user_id == u2.id
        assert res2[1].distance > 100

def test_update_location_coords_unauthorized(client):
    response = client.post("/profile/update-location", json={
        "lat": 27.7172, "lng": 85.3240, "label": "KTM"
    })
    # Requires login, should redirect to login page
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

def test_update_location_coords_success(client, user_factory, login, app):
    with app.app_context():
        user = user_factory(email="test@test.com", password="password")
        login("test@test.com", "password")
        
        response = client.post("/profile/update-location", json={
            "lat": 27.7172, "lng": 85.3240, "label": "Kathmandu"
        })
        assert response.status_code == 200
        assert response.json["ok"] is True
        assert response.json["label"] == "Kathmandu"

def test_update_location_coords_invalid_data(client, user_factory, login, app):
    with app.app_context():
        user_factory(email="test@test.com", password="password")
        login("test@test.com", "password")
        
        response = client.post("/profile/update-location", json={"lat": "invalid", "lng": 85.3240})
        assert response.status_code == 400
        assert "Invalid coordinates" in response.json["error"]

def test_update_location_coords_out_of_range(client, user_factory, login, app):
    with app.app_context():
        user_factory(email="test@test.com", password="password")
        login("test@test.com", "password")
        
        response = client.post("/profile/update-location", json={"lat": 100, "lng": 200})
        assert response.status_code == 400
        assert "Coordinates out of range" in response.json["error"]

def test_marketplace_location_filter(client, user_factory, app):
    with app.app_context():
        db = Database()
        cat_id = db.execute("INSERT INTO categories (name, description) VALUES ('Tech', 'Tech')")
        u1 = user_factory(email="u1@test.com")
        u2 = user_factory(email="u2@test.com")
        
        ProfileRepository().save_location_coords(u1.id, 27.7172, 85.3240, "Kathmandu")
        ProfileRepository().save_location_coords(u2.id, 28.2096, 83.9856, "Pokhara")
        
        ps1 = db.execute("INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, %s)", (u1.id, "Python", "offered"))
        ps2 = db.execute("INSERT INTO profile_skills (user_id, skill_name, skill_type) VALUES (%s, %s, %s)", (u2.id, "Java", "offered"))
        
        SkillRepository().create(
            user_id=u1.id, category_id=cat_id, skill_id=ps1, title="Python listing", description="Python", 
            exchange_type="free", credit_cost=0, availability="any", status="approved"
        )
        SkillRepository().create(
            user_id=u2.id, category_id=cat_id, skill_id=ps2, title="Java listing", description="Java", 
            exchange_type="free", credit_cost=0, availability="any", status="approved"
        )

        # Filtering within 10km of Kathmandu
        response = client.get("/listings/?lat=27.7172&lng=85.3240&radius=10")
        assert response.status_code == 200
        assert b"Python listing" in response.data
        assert b"Java listing" not in response.data

        # Filtering within 200km of Kathmandu
        response2 = client.get("/listings/?lat=27.7172&lng=85.3240&radius=200")
        assert response2.status_code == 200
        assert b"Python listing" in response2.data
        assert b"Java listing" in response2.data
