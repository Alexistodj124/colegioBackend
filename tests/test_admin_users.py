"""Tests para CRUD de usuarios: /admin/users"""
from conftest import auth, make_user


def test_list_users(client, admin_token, admin_user):
    r = client.get("/admin/users", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) >= 1
    emails = [u["email"] for u in r.json()]
    assert "admin@test.com" in emails


def test_create_user(client, admin_token):
    r = client.post("/admin/users", headers=auth(admin_token), json={
        "email": "nuevo@test.com",
        "password": "Nuevo123!",
        "full_name": "Nuevo Usuario",
        "roles": ["PADRE"],
    })
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "nuevo@test.com"
    assert body["full_name"] == "Nuevo Usuario"
    assert "PADRE" in body["roles"]


def test_create_user_duplicate_email(client, admin_token, admin_user):
    r = client.post("/admin/users", headers=auth(admin_token), json={
        "email": "admin@test.com",
        "password": "Pass123!",
        "full_name": "Duplicado",
        "roles": [],
    })
    assert r.status_code == 400
    assert "email" in r.json()["detail"].lower()


def test_create_user_short_password(client, admin_token):
    r = client.post("/admin/users", headers=auth(admin_token), json={
        "email": "short@test.com",
        "password": "12345",
        "full_name": "Short Pass",
    })
    assert r.status_code == 400


def test_create_user_empty_email(client, admin_token):
    r = client.post("/admin/users", headers=auth(admin_token), json={
        "email": "",
        "password": "Pass123!",
        "full_name": "No Email",
    })
    assert r.status_code == 400


def test_create_user_empty_name(client, admin_token):
    r = client.post("/admin/users", headers=auth(admin_token), json={
        "email": "valid@test.com",
        "password": "Pass123!",
        "full_name": "  ",
    })
    assert r.status_code == 400


def test_get_user_by_id(client, admin_token, db):
    user = make_user(db, "detalle@test.com", "Pass123!", "Detalle User", "PADRE")
    r = client.get(f"/admin/users/{user.id}", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["email"] == "detalle@test.com"
    assert "PADRE" in r.json()["roles"]


def test_get_user_not_found(client, admin_token):
    r = client.get("/admin/users/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_update_user(client, admin_token, db):
    user = make_user(db, "update@test.com", "Pass123!", "Antes", "PADRE")
    r = client.patch(f"/admin/users/{user.id}", headers=auth(admin_token), json={
        "full_name": "Despues",
        "is_active": False,
    })
    assert r.status_code == 200
    assert r.json()["full_name"] == "Despues"
    assert r.json()["is_active"] is False


def test_update_user_change_roles(client, admin_token, db):
    user = make_user(db, "rolechange@test.com", "Pass123!", "Role User", "PADRE")
    r = client.patch(f"/admin/users/{user.id}", headers=auth(admin_token), json={
        "roles": ["MAESTRO"],
    })
    assert r.status_code == 200
    assert "MAESTRO" in r.json()["roles"]
    assert "PADRE" not in r.json()["roles"]


def test_update_user_duplicate_email(client, admin_token, db):
    make_user(db, "existing@test.com", "Pass123!", "Existing", "PADRE")
    user2 = make_user(db, "another@test.com", "Pass123!", "Another", "PADRE")
    r = client.patch(f"/admin/users/{user2.id}", headers=auth(admin_token), json={
        "email": "existing@test.com",
    })
    assert r.status_code == 400


def test_update_user_not_found(client, admin_token):
    r = client.patch("/admin/users/99999", headers=auth(admin_token), json={
        "full_name": "X",
    })
    assert r.status_code == 404


def test_delete_user(client, admin_token, db):
    user = make_user(db, "borrar@test.com", "Pass123!", "Borrar", "PADRE")
    r = client.delete(f"/admin/users/{user.id}", headers=auth(admin_token))
    assert r.status_code == 204


def test_delete_self_prevented(client, admin_token, admin_user):
    r = client.delete(f"/admin/users/{admin_user.id}", headers=auth(admin_token))
    assert r.status_code == 400
    assert "propia" in r.json()["detail"].lower() or "propia" in r.json()["detail"]


def test_delete_user_not_found(client, admin_token):
    r = client.delete("/admin/users/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_list_roles(client, admin_token):
    r = client.get("/admin/roles", headers=auth(admin_token))
    assert r.status_code == 200
    names = [role["name"] for role in r.json()]
    assert "ADMIN" in names
    assert "PADRE" in names
    assert "MAESTRO" in names
