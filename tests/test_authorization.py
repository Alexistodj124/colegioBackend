"""Tests de autorizacion: verificar que roles no acceden a recursos prohibidos."""
from conftest import auth


# ---- Sin token -> 401 ----

def test_no_token_admin_students(client):
    r = client.get("/admin/students")
    assert r.status_code == 401


def test_no_token_admin_dashboard(client):
    r = client.get("/admin/dashboard")
    assert r.status_code == 401


def test_no_token_parent_students(client):
    r = client.get("/parent/students")
    assert r.status_code == 401


def test_no_token_teacher_dashboard(client):
    r = client.get("/teacher/dashboard")
    assert r.status_code == 401


# ---- Token invalido -> 401 ----

def test_invalid_token(client):
    r = client.get("/admin/students", headers=auth("not.a.valid.token"))
    assert r.status_code == 401


# ---- PADRE no puede acceder a endpoints de MAESTRO (require_role) ----

def test_parent_cannot_access_teacher_dashboard(client, parent_token):
    r = client.get("/teacher/dashboard", headers=auth(parent_token))
    assert r.status_code == 403


def test_parent_cannot_access_teacher_procedures(client, parent_token):
    r = client.get("/teacher/procedures", headers=auth(parent_token))
    assert r.status_code == 403


# ---- MAESTRO no puede acceder a endpoints de PADRE (require_role) ----

def test_teacher_cannot_access_parent_students(client, teacher_token):
    r = client.get("/parent/students", headers=auth(teacher_token))
    assert r.status_code == 403


def test_teacher_cannot_access_parent_invoices(client, teacher_token):
    r = client.get("/parent/students/1/invoices", headers=auth(teacher_token))
    assert r.status_code == 403


def test_teacher_cannot_access_parent_procedures(client, teacher_token):
    r = client.get("/parent/students/1/procedures", headers=auth(teacher_token))
    assert r.status_code == 403


# ---- MAESTRO no puede marcar pagado (requiere invoices:mark_paid) ----

def test_teacher_cannot_mark_paid(client, teacher_token):
    r = client.post("/admin/invoices/1/mark-paid", headers=auth(teacher_token), json={})
    assert r.status_code == 403


# ---- Endpoint publico ----

def test_procedure_types_no_auth_needed(client):
    r = client.get("/procedure-types")
    assert r.status_code == 200
    assert len(r.json()) > 0
