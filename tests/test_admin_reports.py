"""Tests para dashboard, reportes, exportaciones CSV y audit logs"""
from datetime import date
from conftest import auth, make_student, make_invoice, make_procedure, make_program


# ---- GET /admin/dashboard ----

def test_dashboard_empty(client, admin_token):
    r = client.get("/admin/dashboard", headers=auth(admin_token))
    assert r.status_code == 200
    body = r.json()
    assert body["total_students"] == 0
    assert body["pending_invoices"] == 0
    assert body["pending_procedures"] == 0


def test_dashboard_with_data(client, admin_token, db, admin_user):
    s1 = make_student(db, "Alumno 1", status="VIGENTE")
    s2 = make_student(db, "Alumno 2", google_email="a2@g.com", status="ATRASADO")
    s3 = make_student(db, "Alumno 3", google_email="a3@g.com", status="RETIRADO")
    make_invoice(db, s1.id)
    inv2 = make_invoice(db, s2.id, period=date(2025, 2, 1))
    inv2.status = "PAGADO"
    db.add(inv2)
    db.commit()
    make_procedure(db, s1.id, admin_user.id)

    r = client.get("/admin/dashboard", headers=auth(admin_token))
    body = r.json()
    assert body["total_students"] == 3
    assert body["active_students"] == 1
    assert body["late_students"] == 1
    assert body["withdrawn_students"] == 1
    assert body["pending_invoices"] == 1
    assert body["paid_invoices"] == 1
    assert body["pending_procedures"] == 1


# ---- GET /admin/reports/students ----

def test_report_students(client, admin_token, db):
    make_student(db, "Reporter 1")
    make_student(db, "Reporter 2", google_email="r2@g.com")
    r = client.get("/admin/reports/students", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_report_students_filter_status(client, admin_token, db):
    make_student(db, "Activo", status="VIGENTE")
    make_student(db, "Retirado", google_email="ret@g.com", status="RETIRADO")
    r = client.get("/admin/reports/students?status=VIGENTE", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "VIGENTE"


def test_report_students_search(client, admin_token, db):
    make_student(db, "Carlos Garcia")
    make_student(db, "Maria Lopez", google_email="ml@g.com")
    r = client.get("/admin/reports/students?search=Carlos", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert "Carlos" in r.json()[0]["full_name"]


# ---- GET /admin/reports/invoices ----

def test_report_invoices(client, admin_token, db):
    s = make_student(db)
    make_invoice(db, s.id)
    r = client.get("/admin/reports/invoices", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["student_name"] is not None


def test_report_invoices_filter_status(client, admin_token, db):
    s = make_student(db)
    make_invoice(db, s.id)
    inv2 = make_invoice(db, s.id, period=date(2025, 2, 1))
    inv2.status = "PAGADO"
    db.add(inv2)
    db.commit()

    r = client.get("/admin/reports/invoices?status=PENDIENTE", headers=auth(admin_token))
    assert r.status_code == 200
    assert all(i["status"] == "PENDIENTE" for i in r.json())


# ---- GET /admin/reports/procedures ----

def test_report_procedures(client, admin_token, db, admin_user):
    s = make_student(db)
    make_procedure(db, s.id, admin_user.id)
    r = client.get("/admin/reports/procedures", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


# ---- CSV Exports ----

def test_export_students_csv(client, admin_token, db):
    make_student(db, "Export Alumno")
    r = client.get("/admin/export/students", headers=auth(admin_token))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    content = r.text
    assert "Export Alumno" in content
    assert "ID" in content  # header row


def test_export_invoices_csv(client, admin_token, db):
    s = make_student(db, "Alumno Factura")
    make_invoice(db, s.id, amount=999.99)
    r = client.get("/admin/export/invoices", headers=auth(admin_token))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Alumno Factura" in r.text


def test_export_procedures_csv(client, admin_token, db, admin_user):
    s = make_student(db, "Alumno Tramite")
    make_procedure(db, s.id, admin_user.id, procedure_type="SOLVENCIA")
    r = client.get("/admin/export/procedures", headers=auth(admin_token))
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "SOLVENCIA" in r.text


# ---- GET /admin/audit-logs ----

def test_audit_logs_after_create(client, admin_token, db):
    # Crear un alumno via API genera audit log
    s = make_student(db)
    client.post("/admin/procedures", headers=auth(admin_token), json={
        "student_id": s.id,
        "procedure_type": "CONSTANCIA_ESTUDIOS",
    })
    r = client.get("/admin/audit-logs", headers=auth(admin_token))
    assert r.status_code == 200
    assert len(r.json()) >= 1
    actions = [log["action"] for log in r.json()]
    assert "CREATE" in actions


def test_audit_logs_filter_entity(client, admin_token, db):
    s = make_student(db)
    client.post("/admin/procedures", headers=auth(admin_token), json={
        "student_id": s.id,
        "procedure_type": "RETIRO",
    })
    r = client.get("/admin/audit-logs?entity_type=PROCEDURE", headers=auth(admin_token))
    assert r.status_code == 200
    assert all(log["entity_type"] == "PROCEDURE" for log in r.json())
