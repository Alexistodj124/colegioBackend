"""Tests para CRUD de programas: /admin/programs"""
from conftest import auth, make_program


def test_list_programs_empty(client, admin_token):
    r = client.get("/admin/programs", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_create_program(client, admin_token):
    r = client.post("/admin/programs", headers=auth(admin_token), json={
        "name": "Matematicas 101",
        "description": "Curso basico de matematicas",
        "google_classroom_id": "gc-123",
        "google_classroom_link": "https://classroom.google.com/c/123",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Matematicas 101"
    assert body["google_classroom_id"] == "gc-123"
    assert body["is_active"] is True


def test_create_program_missing_name(client, admin_token):
    r = client.post("/admin/programs", headers=auth(admin_token), json={
        "name": "  ",
    })
    assert r.status_code == 400


def test_get_program_by_id(client, admin_token, db):
    prog = make_program(db, "Ciencias Naturales")
    r = client.get(f"/admin/programs/{prog.id}", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["name"] == "Ciencias Naturales"


def test_get_program_not_found(client, admin_token):
    r = client.get("/admin/programs/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_update_program(client, admin_token, db):
    prog = make_program(db, "Nombre Original")
    r = client.patch(f"/admin/programs/{prog.id}", headers=auth(admin_token), json={
        "name": "Nombre Actualizado",
        "is_active": False,
    })
    assert r.status_code == 200
    assert r.json()["name"] == "Nombre Actualizado"
    assert r.json()["is_active"] is False


def test_update_program_not_found(client, admin_token):
    r = client.patch("/admin/programs/99999", headers=auth(admin_token), json={
        "name": "X",
    })
    assert r.status_code == 404


def test_delete_program(client, admin_token, db):
    prog = make_program(db)
    r = client.delete(f"/admin/programs/{prog.id}", headers=auth(admin_token))
    assert r.status_code == 204

    r2 = client.get(f"/admin/programs/{prog.id}", headers=auth(admin_token))
    assert r2.status_code == 404


def test_delete_program_not_found(client, admin_token):
    r = client.delete("/admin/programs/99999", headers=auth(admin_token))
    assert r.status_code == 404
