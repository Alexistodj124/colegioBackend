"""Tests para CRUD de tramites: /admin/procedures"""
from conftest import auth, make_student, make_procedure, make_user


def test_list_procedures_empty(client, admin_token):
    r = client.get("/admin/procedures", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_create_procedure(client, admin_token, db, admin_user):
    s = make_student(db)
    r = client.post("/admin/procedures", headers=auth(admin_token), json={
        "student_id": s.id,
        "procedure_type": "CONSTANCIA_ESTUDIOS",
        "description": "Solicitud de constancia",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["student_id"] == s.id
    assert body["procedure_type"] == "CONSTANCIA_ESTUDIOS"
    assert body["status"] == "PENDIENTE"
    assert body["requested_by"] == admin_user.id


def test_create_procedure_missing_type(client, admin_token, db):
    s = make_student(db)
    r = client.post("/admin/procedures", headers=auth(admin_token), json={
        "student_id": s.id,
        "procedure_type": "  ",
    })
    assert r.status_code == 400


def test_create_procedure_nonexistent_student(client, admin_token):
    r = client.post("/admin/procedures", headers=auth(admin_token), json={
        "student_id": 99999,
        "procedure_type": "CONSTANCIA_ESTUDIOS",
    })
    assert r.status_code == 404


def test_get_procedure_by_id(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.get(f"/admin/procedures/{proc.id}", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["id"] == proc.id
    assert r.json()["student_name"] == s.full_name


def test_get_procedure_not_found(client, admin_token):
    r = client.get("/admin/procedures/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_update_procedure_status(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.patch(f"/admin/procedures/{proc.id}", headers=auth(admin_token), json={
        "status": "EN_PROCESO",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "EN_PROCESO"


def test_update_procedure_invalid_status(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.patch(f"/admin/procedures/{proc.id}", headers=auth(admin_token), json={
        "status": "INVALIDO",
    })
    assert r.status_code == 400


def test_update_procedure_approve(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.patch(f"/admin/procedures/{proc.id}", headers=auth(admin_token), json={
        "status": "APROBADO",
        "notes": "Aprobado por admin",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "APROBADO"
    assert body["approved_by"] == admin_user.id
    assert body["approved_at"] is not None
    assert body["notes"] == "Aprobado por admin"


def test_update_procedure_reject(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.patch(f"/admin/procedures/{proc.id}", headers=auth(admin_token), json={
        "status": "RECHAZADO",
        "notes": "Documentos incompletos",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "RECHAZADO"


def test_update_procedure_assign(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    teacher = make_user(db, "teacher2@test.com", "Pass123!", "Teacher 2", "MAESTRO")
    r = client.patch(f"/admin/procedures/{proc.id}", headers=auth(admin_token), json={
        "assigned_to": teacher.id,
    })
    assert r.status_code == 200
    assert r.json()["assigned_to"] == teacher.id
    assert r.json()["assigned_to_name"] == "Teacher 2"


def test_update_procedure_not_found(client, admin_token):
    r = client.patch("/admin/procedures/99999", headers=auth(admin_token), json={
        "status": "EN_PROCESO",
    })
    assert r.status_code == 404


def test_delete_procedure(client, admin_token, db, admin_user):
    s = make_student(db)
    proc = make_procedure(db, s.id, admin_user.id)
    r = client.delete(f"/admin/procedures/{proc.id}", headers=auth(admin_token))
    assert r.status_code == 204


def test_delete_procedure_not_found(client, admin_token):
    r = client.delete("/admin/procedures/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_filter_procedures_by_status(client, admin_token, db, admin_user):
    s = make_student(db)
    make_procedure(db, s.id, admin_user.id)  # PENDIENTE
    proc2 = make_procedure(db, s.id, admin_user.id, procedure_type="SOLVENCIA")
    # Aprobar proc2 directamente
    proc2.status = "APROBADO"
    db.add(proc2)
    db.commit()

    r = client.get("/admin/procedures?status=PENDIENTE", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "PENDIENTE"


def test_get_assignable_users(client, admin_token, db, admin_user):
    teacher = make_user(db, "asignable@test.com", "Pass123!", "Maestro Asignable", "MAESTRO")
    r = client.get("/admin/assignable-users", headers=auth(admin_token))
    assert r.status_code == 200
    names = [u["full_name"] for u in r.json()]
    assert "Maestro Asignable" in names
    assert "Admin User" in names  # admins tambien son asignables


def test_procedure_types_endpoint(client):
    """El endpoint /procedure-types es publico"""
    r = client.get("/procedure-types")
    assert r.status_code == 200
    codes = [t["code"] for t in r.json()]
    assert "CONSTANCIA_ESTUDIOS" in codes
    assert "RETIRO" in codes
