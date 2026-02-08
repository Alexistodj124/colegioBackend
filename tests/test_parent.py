"""Tests para endpoints de PADRE: /parent/*"""
from conftest import auth, make_student, make_invoice, make_procedure, link_parent


# ---- GET /parent/students ----

def test_parent_list_students(client, parent_token, db, parent_user):
    s = make_student(db, "Hijo de Padre")
    link_parent(db, parent_user.id, s.id)
    r = client.get("/parent/students", headers=auth(parent_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["full_name"] == "Hijo de Padre"
    assert r.json()[0]["relationship"] == "Padre/Madre"


def test_parent_no_children(client, parent_token):
    r = client.get("/parent/students", headers=auth(parent_token))
    assert r.status_code == 200
    assert r.json() == []


# ---- GET /parent/students/{id}/invoices ----

def test_parent_view_invoices(client, parent_token, db, parent_user):
    s = make_student(db, "Hijo Facturas")
    link_parent(db, parent_user.id, s.id)
    make_invoice(db, s.id, amount=300)
    r = client.get(f"/parent/students/{s.id}/invoices", headers=auth(parent_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["amount"] == 300.0


def test_parent_view_invoices_not_their_child(client, parent_token, db):
    s = make_student(db, "Otro Hijo")
    # No vinculamos al padre
    r = client.get(f"/parent/students/{s.id}/invoices", headers=auth(parent_token))
    assert r.status_code == 404


# ---- GET /parent/students/{id}/procedures ----

def test_parent_view_procedures(client, parent_token, db, parent_user):
    s = make_student(db, "Hijo Tramites")
    link_parent(db, parent_user.id, s.id)
    make_procedure(db, s.id, parent_user.id)
    r = client.get(f"/parent/students/{s.id}/procedures", headers=auth(parent_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_parent_view_procedures_not_their_child(client, parent_token, db):
    s = make_student(db, "No Es Mi Hijo")
    r = client.get(f"/parent/students/{s.id}/procedures", headers=auth(parent_token))
    assert r.status_code == 404


# ---- POST /parent/students/{id}/procedures ----

def test_parent_create_procedure(client, parent_token, db, parent_user):
    s = make_student(db, "Hijo Para Tramite")
    link_parent(db, parent_user.id, s.id)
    r = client.post(f"/parent/students/{s.id}/procedures", headers=auth(parent_token), json={
        "student_id": s.id,
        "procedure_type": "CONSTANCIA_ESTUDIOS",
        "description": "Necesito constancia",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["procedure_type"] == "CONSTANCIA_ESTUDIOS"
    assert body["status"] == "PENDIENTE"
    assert body["requested_by"] == parent_user.id


def test_parent_create_procedure_invalid_type(client, parent_token, db, parent_user):
    s = make_student(db, "Hijo Tipo Invalido")
    link_parent(db, parent_user.id, s.id)
    r = client.post(f"/parent/students/{s.id}/procedures", headers=auth(parent_token), json={
        "student_id": s.id,
        "procedure_type": "TIPO_INVENTADO",
    })
    assert r.status_code == 400


def test_parent_create_procedure_for_non_child(client, parent_token, db):
    s = make_student(db, "No Vinculado")
    r = client.post(f"/parent/students/{s.id}/procedures", headers=auth(parent_token), json={
        "student_id": s.id,
        "procedure_type": "SOLVENCIA",
    })
    assert r.status_code == 404
