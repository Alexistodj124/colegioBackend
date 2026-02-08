"""Tests para CRUD de alumnos: /admin/students"""
from conftest import auth, make_student


def test_list_students_empty(client, admin_token):
    r = client.get("/admin/students", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_create_student(client, admin_token):
    r = client.post("/admin/students", headers=auth(admin_token), json={
        "full_name": "Juan Perez",
        "google_email": "juan@google.com",
        "status": "VIGENTE",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["full_name"] == "Juan Perez"
    assert body["google_email"] == "juan@google.com"
    assert body["status"] == "VIGENTE"
    assert "id" in body


def test_create_student_missing_name(client, admin_token):
    r = client.post("/admin/students", headers=auth(admin_token), json={
        "full_name": "  ",
        "google_email": "x@g.com",
    })
    assert r.status_code == 400


def test_list_students_after_create(client, admin_token, db):
    make_student(db, "Maria Lopez")
    r = client.get("/admin/students", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["full_name"] == "Maria Lopez"


def test_get_student_by_id(client, admin_token, db):
    s = make_student(db, "Carlos Ramirez")
    r = client.get(f"/admin/students/{s.id}", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["full_name"] == "Carlos Ramirez"


def test_get_student_not_found(client, admin_token):
    r = client.get("/admin/students/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_update_student_name(client, admin_token, db):
    s = make_student(db, "Original Name")
    r = client.patch(f"/admin/students/{s.id}", headers=auth(admin_token), json={
        "full_name": "Updated Name",
    })
    assert r.status_code == 200
    assert r.json()["full_name"] == "Updated Name"


def test_update_student_status(client, admin_token, db):
    s = make_student(db, "Alumno Activo")
    r = client.patch(f"/admin/students/{s.id}", headers=auth(admin_token), json={
        "status": "ATRASADO",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ATRASADO"


def test_update_student_invalid_status(client, admin_token, db):
    s = make_student(db)
    r = client.patch(f"/admin/students/{s.id}", headers=auth(admin_token), json={
        "status": "INVALIDO",
    })
    assert r.status_code == 400


def test_update_student_not_found(client, admin_token):
    r = client.patch("/admin/students/99999", headers=auth(admin_token), json={
        "full_name": "X",
    })
    assert r.status_code == 404


def test_delete_student(client, admin_token, db):
    s = make_student(db)
    r = client.delete(f"/admin/students/{s.id}", headers=auth(admin_token))
    assert r.status_code == 204

    r2 = client.get(f"/admin/students/{s.id}", headers=auth(admin_token))
    assert r2.status_code == 404


def test_delete_student_not_found(client, admin_token):
    r = client.delete("/admin/students/99999", headers=auth(admin_token))
    assert r.status_code == 404
