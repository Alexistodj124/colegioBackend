"""Tests para endpoints de autenticacion: /auth/login y /auth/me"""
from conftest import auth, make_user


# ---- POST /auth/login ----

def test_login_success(client, admin_user):
    r = client.post("/auth/login", json={"email": "admin@test.com", "password": "Admin123!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "admin@test.com"
    assert "ADMIN" in body["roles"]
    assert "students:read" in body["permissions"]


def test_login_wrong_password(client, admin_user):
    r = client.post("/auth/login", json={"email": "admin@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_login_nonexistent_email(client):
    r = client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401


def test_login_inactive_user(client, db):
    user = make_user(db, "inactive@test.com", "Pass123!", "Inactive", "ADMIN")
    user.is_active = False
    db.add(user)
    db.commit()

    r = client.post("/auth/login", json={"email": "inactive@test.com", "password": "Pass123!"})
    assert r.status_code == 401


def test_login_case_insensitive_email(client, admin_user):
    r = client.post("/auth/login", json={"email": "ADMIN@TEST.COM", "password": "Admin123!"})
    assert r.status_code == 200


# ---- GET /auth/me ----

def test_me_success(client, admin_token):
    r = client.get("/auth/me", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "admin@test.com"
    assert "ADMIN" in body["roles"]


def test_me_no_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_invalid_token(client):
    r = client.get("/auth/me", headers=auth("invalid.token.here"))
    assert r.status_code == 401
