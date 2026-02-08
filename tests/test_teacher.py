"""Tests para endpoints de MAESTRO: /teacher/*"""
from conftest import auth, make_student, make_procedure, make_user


# ---- GET /teacher/dashboard ----

def test_teacher_dashboard_empty(client, teacher_token):
    r = client.get("/teacher/dashboard", headers=auth(teacher_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total_assigned"] == 0
    assert body["pending_procedures"] == 0


def test_teacher_dashboard_with_data(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    r = client.get("/teacher/dashboard", headers=auth(teacher_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total_assigned"] == 1
    assert body["pending_procedures"] == 1


# ---- GET /teacher/procedures ----

def test_teacher_list_procedures(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    # Otro tramite NO asignado al maestro
    make_procedure(db, s.id, admin_user.id, procedure_type="SOLVENCIA")

    r = client.get("/teacher/procedures", headers=auth(teacher_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == proc.id


def test_teacher_list_procedures_filter_status(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    r = client.get("/teacher/procedures?status=PENDIENTE", headers=auth(teacher_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---- PATCH /teacher/procedures/{id} ----

def test_teacher_update_assigned_procedure(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    r = client.patch(f"/teacher/procedures/{proc.id}", headers=auth(teacher_token), json={
        "status": "EN_PROCESO",
        "notes": "Revisando documentos",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "EN_PROCESO"
    assert r.json()["notes"] == "Revisando documentos"


def test_teacher_approve_procedure(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    r = client.patch(f"/teacher/procedures/{proc.id}", headers=auth(teacher_token), json={
        "status": "APROBADO",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "APROBADO"
    assert r.json()["approved_by"] == teacher_user.id


def test_teacher_update_not_assigned_procedure(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    # Tramite asignado a otro usuario
    other_teacher = make_user(db, "other@test.com", "Pass123!", "Other", "MAESTRO")
    proc = make_procedure(db, s.id, admin_user.id, assigned_to=other_teacher.id)
    r = client.patch(f"/teacher/procedures/{proc.id}", headers=auth(teacher_token), json={
        "status": "EN_PROCESO",
    })
    assert r.status_code == 403


def test_teacher_update_nonexistent_procedure(client, teacher_token):
    r = client.patch("/teacher/procedures/99999", headers=auth(teacher_token), json={
        "status": "EN_PROCESO",
    })
    assert r.status_code == 404


def test_teacher_update_invalid_status(client, teacher_token, db, teacher_user, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id, assigned_to=teacher_user.id)
    r = client.patch(f"/teacher/procedures/{proc.id}", headers=auth(teacher_token), json={
        "status": "INVALIDO",
    })
    assert r.status_code == 400
