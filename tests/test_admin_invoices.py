"""Tests para CRUD de mensualidades: /admin/invoices"""
from conftest import auth, make_student, make_invoice


def test_list_invoices_empty(client, admin_token):
    r = client.get("/admin/invoices", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json() == []


def test_create_invoice(client, admin_token, db):
    s = make_student(db)
    r = client.post("/admin/invoices", headers=auth(admin_token), json={
        "student_id": s.id,
        "period": "2025-03-01",
        "amount": 750.00,
    })
    assert r.status_code == 201
    body = r.json()
    assert body["student_id"] == s.id
    assert body["amount"] == 750.0
    assert body["status"] == "PENDIENTE"
    # Debe usar payment_url por defecto
    assert "pagos" in body["payment_url"]


def test_create_invoice_custom_payment_url(client, admin_token, db):
    s = make_student(db)
    r = client.post("/admin/invoices", headers=auth(admin_token), json={
        "student_id": s.id,
        "period": "2025-04-01",
        "amount": 500.00,
        "payment_url": "https://custom.pay/link",
    })
    assert r.status_code == 201
    assert r.json()["payment_url"] == "https://custom.pay/link"


def test_create_invoice_amount_zero(client, admin_token, db):
    s = make_student(db)
    r = client.post("/admin/invoices", headers=auth(admin_token), json={
        "student_id": s.id,
        "period": "2025-01-01",
        "amount": 0,
    })
    assert r.status_code == 400


def test_create_invoice_negative_amount(client, admin_token, db):
    s = make_student(db)
    r = client.post("/admin/invoices", headers=auth(admin_token), json={
        "student_id": s.id,
        "period": "2025-01-01",
        "amount": -100,
    })
    assert r.status_code == 400


def test_create_invoice_nonexistent_student(client, admin_token):
    r = client.post("/admin/invoices", headers=auth(admin_token), json={
        "student_id": 99999,
        "period": "2025-01-01",
        "amount": 500,
    })
    assert r.status_code == 404


def test_update_invoice(client, admin_token, db):
    s = make_student(db)
    inv = make_invoice(db, s.id)
    r = client.patch(f"/admin/invoices/{inv.id}", headers=auth(admin_token), json={
        "payment_url": "https://new-url.com",
    })
    assert r.status_code == 200
    assert r.json()["payment_url"] == "https://new-url.com"


def test_update_invoice_invalid_status(client, admin_token, db):
    s = make_student(db)
    inv = make_invoice(db, s.id)
    r = client.patch(f"/admin/invoices/{inv.id}", headers=auth(admin_token), json={
        "status": "INVALIDO",
    })
    assert r.status_code == 400


def test_update_invoice_not_found(client, admin_token):
    r = client.patch("/admin/invoices/99999", headers=auth(admin_token), json={
        "status": "PAGADO",
    })
    assert r.status_code == 404


def test_delete_invoice(client, admin_token, db):
    s = make_student(db)
    inv = make_invoice(db, s.id)
    r = client.delete(f"/admin/invoices/{inv.id}", headers=auth(admin_token))
    assert r.status_code == 204


def test_delete_invoice_not_found(client, admin_token):
    r = client.delete("/admin/invoices/99999", headers=auth(admin_token))
    assert r.status_code == 404


def test_mark_invoice_paid(client, admin_token, db):
    s = make_student(db)
    inv = make_invoice(db, s.id)
    r = client.post(f"/admin/invoices/{inv.id}/mark-paid", headers=auth(admin_token), json={
        "external_payment_id": "PAY-12345",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PAGADO"
    assert body["paid_at"] is not None


def test_mark_paid_not_found(client, admin_token):
    r = client.post("/admin/invoices/99999/mark-paid", headers=auth(admin_token), json={})
    assert r.status_code == 404
