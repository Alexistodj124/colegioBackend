from fastapi import FastAPI, Depends, HTTPException, status, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from datetime import date
from typing import Optional
import csv
import io

from db import Base, engine
import crud
from deps import get_db, get_current_user, require_role, require_permission
from security import verify_password, create_access_token
from schemas import (
    LoginRequest, TokenResponse, MeResponse,
    StudentOut, InvoiceOut, MarkPaidRequest,
    StudentCreate, StudentUpdate, StudentDetail,
    ProcedureCreate, ProcedureUpdate, ProcedureOut, ProcedureTypeOut,
    InvoiceCreate, InvoiceUpdate, DashboardStats,
    ProgramCreate, ProgramUpdate, ProgramOut,
    UserCreate, UserUpdate, UserOut,
    AuditLogOut
)
from models import PROCEDURE_TYPES

app = FastAPI(title="Portal Educativo API (MVP)")
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Crea tablas (para MVP). En producción: migraciones (Alembic).
Base.metadata.create_all(bind=engine)

# ======================
# Helper Functions
# ======================
def _format_procedure(db: Session, p):
    """Formatea un trámite con nombres de usuarios"""
    student = crud.get_student_by_id(db, p.student_id)
    requested_by_user = crud.get_user_by_id(db, p.requested_by) if p.requested_by else None
    assigned_to_user = crud.get_user_by_id(db, p.assigned_to) if p.assigned_to else None
    approved_by_user = crud.get_user_by_id(db, p.approved_by) if p.approved_by else None

    return {
        "id": p.id,
        "student_id": p.student_id,
        "student_name": student.full_name if student else None,
        "procedure_type": p.procedure_type,
        "description": p.description,
        "status": p.status,
        "requested_by": p.requested_by,
        "requested_by_name": requested_by_user.full_name if requested_by_user else None,
        "assigned_to": p.assigned_to,
        "assigned_to_name": assigned_to_user.full_name if assigned_to_user else None,
        "approved_by": p.approved_by,
        "approved_by_name": approved_by_user.full_name if approved_by_user else None,
        "approved_at": p.approved_at,
        "notes": p.notes,
        "created_at": p.created_at,
        "updated_at": p.updated_at
    }

@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_email(db, body.email.strip().lower())
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    roles, perms = crud.get_roles_and_permissions(db, user.id)
    token = create_access_token(str(user.id))

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name},
        "roles": roles,
        "permissions": perms
    }

@app.get("/auth/me", response_model=MeResponse)
def me(ctx = Depends(get_current_user)):
    return {
        "user": {"id": ctx["id"], "email": ctx["email"], "full_name": ctx["full_name"]},
        "roles": ctx["roles"],
        "permissions": ctx["permissions"]
    }

# ======================
# PADRE: Hijos + Estado
# ======================
@app.get("/parent/students", response_model=list[StudentOut])
def parent_students(
    ctx = Depends(require_role("PADRE")),
    db: Session = Depends(get_db)
):
    rows = crud.parent_get_students(db, ctx["id"])
    return [
        {
            "student_id": r.student_id,
            "full_name": r.full_name,
            "status": r.status,
            "relationship": r.relationship
        } for r in rows
    ]

@app.get("/parent/students/{student_id}/invoices", response_model=list[InvoiceOut])
def parent_invoices(
    student_id: int,
    ctx = Depends(require_role("PADRE")),
    db: Session = Depends(get_db)
):
    if not crud.parent_student_belongs(db, ctx["id"], student_id):
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    rows = crud.parent_get_invoices(db, student_id)
    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "period": r.period,
            "amount": float(r.amount),
            "status": r.status,
            "payment_url": r.payment_url,
            "paid_at": r.paid_at
        } for r in rows
    ]

# ======================
# PADRE: Solicitar Trámites
# ======================
@app.get("/procedure-types", response_model=list[ProcedureTypeOut])
def get_procedure_types():
    """Retorna el catálogo de tipos de trámite disponibles"""
    return PROCEDURE_TYPES

@app.get("/parent/students/{student_id}/procedures", response_model=list[ProcedureOut])
def parent_student_procedures(
    student_id: int,
    ctx = Depends(require_role("PADRE")),
    db: Session = Depends(get_db)
):
    """Ver trámites de un hijo"""
    if not crud.parent_student_belongs(db, ctx["id"], student_id):
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    procedures = crud.get_procedures_by_student(db, student_id)
    return [_format_procedure(db, p) for p in procedures]

@app.post("/parent/students/{student_id}/procedures", response_model=ProcedureOut, status_code=status.HTTP_201_CREATED)
def parent_create_procedure(
    student_id: int,
    body: ProcedureCreate,
    ctx = Depends(require_role("PADRE")),
    db: Session = Depends(get_db)
):
    """Padre solicita un trámite para su hijo"""
    if not crud.parent_student_belongs(db, ctx["id"], student_id):
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    valid_types = [t["code"] for t in PROCEDURE_TYPES]
    if body.procedure_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Tipo de trámite inválido. Opciones: {', '.join(valid_types)}")

    procedure = crud.create_procedure(
        db,
        student_id=student_id,
        procedure_type=body.procedure_type,
        description=body.description,
        requested_by=ctx["id"]
    )

    crud.create_audit_log(db, ctx["id"], "CREATE", "PROCEDURE", procedure.id, f"Padre solicitó trámite: {body.procedure_type}")

    return _format_procedure(db, procedure)

# ======================
# ADMIN: Marcar PAGADO
# ======================
@app.post("/admin/invoices/{invoice_id}/mark-paid", response_model=InvoiceOut)
def admin_mark_paid(
    invoice_id: int,
    body: MarkPaidRequest,
    _ctx = Depends(require_permission("invoices:mark_paid")),
    db: Session = Depends(get_db)
):
    inv = crud.admin_mark_invoice_paid(db, invoice_id, body.external_payment_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Mensualidad no encontrada")

    return {
        "id": inv.id,
        "student_id": inv.student_id,
        "period": inv.period,
        "amount": float(inv.amount),
        "status": inv.status,
        "payment_url": inv.payment_url,
        "paid_at": inv.paid_at
    }

# ======================
# ADMIN: Students CRUD
# ======================
@app.get("/admin/students", response_model=list[StudentDetail])
def admin_list_students(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    students = crud.get_all_students(db)
    return students

@app.get("/admin/students/{student_id}", response_model=StudentDetail)
def admin_get_student(
    student_id: int,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    student = crud.get_student_by_id(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    return student

@app.post("/admin/students", response_model=StudentDetail, status_code=status.HTTP_201_CREATED)
def admin_create_student(
    body: StudentCreate,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if not body.full_name or not body.full_name.strip():
        raise HTTPException(status_code=400, detail="El nombre completo es requerido")

    student = crud.create_student(
        db,
        full_name=body.full_name.strip(),
        google_email=body.google_email.strip() if body.google_email else None,
        status=body.status or "VIGENTE"
    )
    return student

@app.patch("/admin/students/{student_id}", response_model=StudentDetail)
def admin_update_student(
    student_id: int,
    body: StudentUpdate,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if body.status and body.status not in ["VIGENTE", "ATRASADO", "RETIRADO"]:
        raise HTTPException(status_code=400, detail="Estado inválido")

    student = crud.update_student(
        db, student_id,
        full_name=body.full_name.strip() if body.full_name else None,
        google_email=body.google_email.strip() if body.google_email else None,
        status=body.status
    )
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")
    return student

@app.delete("/admin/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_student(
    student_id: int,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    deleted = crud.delete_student(db, student_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

# ======================
# ADMIN: Procedures CRUD
# ======================
@app.get("/admin/procedures", response_model=list[ProcedureOut])
def admin_list_procedures(
    status: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    assigned_to: Optional[int] = Query(None),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if status:
        filters["status"] = status
    if student_id:
        filters["student_id"] = student_id
    if assigned_to:
        filters["assigned_to"] = assigned_to

    procedures = crud.get_all_procedures(db, filters if filters else None)
    return [_format_procedure(db, p) for p in procedures]

@app.get("/admin/procedures/{procedure_id}", response_model=ProcedureOut)
def admin_get_procedure(
    procedure_id: int,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    procedure = crud.get_procedure_by_id(db, procedure_id)
    if not procedure:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")
    return _format_procedure(db, procedure)

@app.post("/admin/procedures", response_model=ProcedureOut, status_code=status.HTTP_201_CREATED)
def admin_create_procedure(
    body: ProcedureCreate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if not body.procedure_type or not body.procedure_type.strip():
        raise HTTPException(status_code=400, detail="El tipo de trámite es requerido")

    student = crud.get_student_by_id(db, body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    procedure = crud.create_procedure(
        db,
        student_id=body.student_id,
        procedure_type=body.procedure_type.strip(),
        description=body.description,
        requested_by=ctx["id"]
    )

    crud.create_audit_log(db, ctx["id"], "CREATE", "PROCEDURE", procedure.id, f"Admin creó trámite: {body.procedure_type}")

    return _format_procedure(db, procedure)

@app.patch("/admin/procedures/{procedure_id}", response_model=ProcedureOut)
def admin_update_procedure(
    procedure_id: int,
    body: ProcedureUpdate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if body.status and body.status not in ["PENDIENTE", "EN_PROCESO", "APROBADO", "RECHAZADO"]:
        raise HTTPException(status_code=400, detail="Estado inválido")

    # Validar que el usuario asignado existe y es MAESTRO o ADMIN
    if body.assigned_to:
        assigned_user = crud.get_user_by_id(db, body.assigned_to)
        if not assigned_user:
            raise HTTPException(status_code=400, detail="Usuario asignado no encontrado")

    procedure = crud.update_procedure(
        db, procedure_id,
        status=body.status,
        notes=body.notes,
        approved_by=ctx["id"] if body.status in ["APROBADO", "RECHAZADO"] else None,
        assigned_to=body.assigned_to
    )
    if not procedure:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")

    crud.create_audit_log(db, ctx["id"], "UPDATE", "PROCEDURE", procedure_id, f"Status: {body.status}, Asignado a: {body.assigned_to}")

    return _format_procedure(db, procedure)

@app.delete("/admin/procedures/{procedure_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_procedure(
    procedure_id: int,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    crud.create_audit_log(db, ctx["id"], "DELETE", "PROCEDURE", procedure_id, "Trámite eliminado")
    deleted = crud.delete_procedure(db, procedure_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")

# Obtener usuarios disponibles para asignar (maestros y admins)
@app.get("/admin/assignable-users")
def admin_get_assignable_users(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    """Retorna usuarios que pueden ser asignados a trámites (MAESTRO y ADMIN)"""
    teachers = crud.get_users_by_role(db, "MAESTRO")
    admins = crud.get_users_by_role(db, "ADMIN")

    users = []
    seen_ids = set()
    for user in teachers + admins:
        if user.id not in seen_ids:
            roles, _ = crud.get_roles_and_permissions(db, user.id)
            users.append({
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "roles": roles
            })
            seen_ids.add(user.id)

    return users

# ======================
# ADMIN: Invoices CRUD
# ======================
@app.get("/admin/invoices", response_model=list[InvoiceOut])
def admin_list_invoices(
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    invoices = crud.get_all_invoices(db)
    return [
        {
            "id": inv.id,
            "student_id": inv.student_id,
            "period": inv.period,
            "amount": float(inv.amount),
            "status": inv.status,
            "payment_url": inv.payment_url,
            "paid_at": inv.paid_at
        } for inv in invoices
    ]

# Link genérico de pago (placeholder hasta que se integre la plataforma de pagos)
DEFAULT_PAYMENT_URL = "https://pagos.colegio.edu.gt/pagar"

@app.post("/admin/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def admin_create_invoice(
    body: InvoiceCreate,
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")

    # Si no se proporciona URL de pago, usar el link genérico
    payment_url = body.payment_url.strip() if body.payment_url and body.payment_url.strip() else DEFAULT_PAYMENT_URL

    student = crud.get_student_by_id(db, body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Alumno no encontrado")

    try:
        invoice = crud.create_invoice(
            db,
            student_id=body.student_id,
            period=body.period,
            amount=body.amount,
            payment_url=payment_url
        )
        return {
            "id": invoice.id,
            "student_id": invoice.student_id,
            "period": invoice.period,
            "amount": float(invoice.amount),
            "status": invoice.status,
            "payment_url": invoice.payment_url,
            "paid_at": invoice.paid_at
        }
    except Exception as e:
        if "uq_invoice_student_period" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe una mensualidad para este alumno en ese periodo")
        raise

@app.patch("/admin/invoices/{invoice_id}", response_model=InvoiceOut)
def admin_update_invoice(
    invoice_id: int,
    body: InvoiceUpdate,
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    if body.status and body.status not in ["PENDIENTE", "PAGADO"]:
        raise HTTPException(status_code=400, detail="Estado inválido")

    invoice = crud.update_invoice(
        db, invoice_id,
        status=body.status,
        payment_url=body.payment_url
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Mensualidad no encontrada")

    return {
        "id": invoice.id,
        "student_id": invoice.student_id,
        "period": invoice.period,
        "amount": float(invoice.amount),
        "status": invoice.status,
        "payment_url": invoice.payment_url,
        "paid_at": invoice.paid_at
    }

@app.delete("/admin/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_invoice(
    invoice_id: int,
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    deleted = crud.delete_invoice(db, invoice_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mensualidad no encontrada")

# ======================
# ADMIN: Dashboard
# ======================
@app.get("/admin/dashboard", response_model=DashboardStats)
def admin_dashboard(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    return crud.get_dashboard_stats(db)

# ======================
# TEACHER: Dashboard & Procedures
# ======================
@app.get("/teacher/dashboard")
def teacher_dashboard(
    ctx = Depends(require_role("MAESTRO")),
    db: Session = Depends(get_db)
):
    # Estadísticas de trámites asignados al maestro
    all_procedures = crud.get_all_procedures(db)
    my_procedures = [p for p in all_procedures if p.assigned_to == ctx["id"]]

    pending = sum(1 for p in my_procedures if p.status == "PENDIENTE")
    in_process = sum(1 for p in my_procedures if p.status == "EN_PROCESO")
    approved = sum(1 for p in my_procedures if p.status == "APROBADO")
    rejected = sum(1 for p in my_procedures if p.status == "RECHAZADO")

    return {
        "pending_procedures": pending,
        "in_process_procedures": in_process,
        "approved_procedures": approved,
        "rejected_procedures": rejected,
        "total_assigned": len(my_procedures)
    }

@app.get("/teacher/procedures", response_model=list[ProcedureOut])
def teacher_list_procedures(
    status: Optional[str] = Query(None),
    ctx = Depends(require_role("MAESTRO")),
    db: Session = Depends(get_db)
):
    """Lista los trámites asignados al maestro"""
    filters = {"assigned_to": ctx["id"]}
    if status:
        filters["status"] = status

    procedures = crud.get_all_procedures(db, filters)
    return [_format_procedure(db, p) for p in procedures]

@app.patch("/teacher/procedures/{procedure_id}", response_model=ProcedureOut)
def teacher_update_procedure(
    procedure_id: int,
    body: ProcedureUpdate,
    ctx = Depends(require_role("MAESTRO")),
    db: Session = Depends(get_db)
):
    # Verificar que el trámite está asignado al maestro
    procedure = crud.get_procedure_by_id(db, procedure_id)
    if not procedure:
        raise HTTPException(status_code=404, detail="Trámite no encontrado")

    if procedure.assigned_to != ctx["id"]:
        raise HTTPException(status_code=403, detail="Este trámite no está asignado a ti")

    if body.status and body.status not in ["PENDIENTE", "EN_PROCESO", "APROBADO", "RECHAZADO"]:
        raise HTTPException(status_code=400, detail="Estado inválido")

    procedure = crud.update_procedure(
        db, procedure_id,
        status=body.status,
        notes=body.notes,
        approved_by=ctx["id"] if body.status in ["APROBADO", "RECHAZADO"] else None
    )

    crud.create_audit_log(db, ctx["id"], "UPDATE", "PROCEDURE", procedure_id, f"Maestro actualizó trámite: {body.status}")

    return _format_procedure(db, procedure)


# ======================
# ADMIN: Programs CRUD
# ======================
@app.get("/admin/programs", response_model=list[ProgramOut])
def admin_list_programs(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    programs = crud.get_all_programs(db)
    return programs

@app.get("/admin/programs/{program_id}", response_model=ProgramOut)
def admin_get_program(
    program_id: int,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    program = crud.get_program_by_id(db, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")
    return program

@app.post("/admin/programs", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
def admin_create_program(
    body: ProgramCreate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="El nombre del programa es requerido")

    program = crud.create_program(
        db,
        name=body.name.strip(),
        description=body.description,
        google_classroom_id=body.google_classroom_id,
        google_classroom_link=body.google_classroom_link
    )

    crud.create_audit_log(db, ctx["id"], "CREATE", "PROGRAM", program.id, f"Programa creado: {body.name}")

    return program

@app.patch("/admin/programs/{program_id}", response_model=ProgramOut)
def admin_update_program(
    program_id: int,
    body: ProgramUpdate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    program = crud.update_program(
        db, program_id,
        name=body.name.strip() if body.name else None,
        description=body.description,
        google_classroom_id=body.google_classroom_id,
        google_classroom_link=body.google_classroom_link,
        is_active=body.is_active
    )
    if not program:
        raise HTTPException(status_code=404, detail="Programa no encontrado")

    crud.create_audit_log(db, ctx["id"], "UPDATE", "PROGRAM", program_id, f"Programa actualizado")

    return program

@app.delete("/admin/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_program(
    program_id: int,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    crud.create_audit_log(db, ctx["id"], "DELETE", "PROGRAM", program_id, "Programa eliminado")
    deleted = crud.delete_program(db, program_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Programa no encontrado")


# ======================
# ADMIN: Users CRUD
# ======================
@app.get("/admin/users", response_model=list[UserOut])
def admin_list_users(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    users = crud.get_all_users(db)
    result = []
    for user in users:
        roles, _ = crud.get_roles_and_permissions(db, user.id)
        result.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "roles": roles,
            "created_at": user.created_at
        })
    return result

@app.get("/admin/users/{user_id}", response_model=UserOut)
def admin_get_user(
    user_id: int,
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    roles, _ = crud.get_roles_and_permissions(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "roles": roles,
        "created_at": user.created_at
    }

@app.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    body: UserCreate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if not body.email or not body.email.strip():
        raise HTTPException(status_code=400, detail="El email es requerido")
    if not body.password or len(body.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if not body.full_name or not body.full_name.strip():
        raise HTTPException(status_code=400, detail="El nombre completo es requerido")

    existing = crud.get_user_by_email(db, body.email.strip().lower())
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = crud.create_user(
        db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role_names=body.roles
    )

    crud.create_audit_log(db, ctx["id"], "CREATE", "USER", user.id, f"Usuario creado: {body.email}")

    roles, _ = crud.get_roles_and_permissions(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "roles": roles,
        "created_at": user.created_at
    }

@app.patch("/admin/users/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: int,
    body: UserUpdate,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if body.email:
        existing = crud.get_user_by_email(db, body.email.strip().lower())
        if existing and existing.id != user_id:
            raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    user = crud.update_user(
        db, user_id,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        is_active=body.is_active,
        role_names=body.roles
    )
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    crud.create_audit_log(db, ctx["id"], "UPDATE", "USER", user_id, f"Usuario actualizado")

    roles, _ = crud.get_roles_and_permissions(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "roles": roles,
        "created_at": user.created_at
    }

@app.delete("/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    if user_id == ctx["id"]:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    crud.create_audit_log(db, ctx["id"], "DELETE", "USER", user_id, "Usuario eliminado")
    deleted = crud.delete_user(db, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

@app.get("/admin/roles")
def admin_list_roles(
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    """Lista todos los roles disponibles"""
    roles = crud.get_all_roles(db)
    return [{"id": r.id, "name": r.name} for r in roles]


# ======================
# ADMIN: Audit Logs
# ======================
@app.get("/admin/audit-logs", response_model=list[AuditLogOut])
def admin_list_audit_logs(
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if entity_type:
        filters["entity_type"] = entity_type
    if action:
        filters["action"] = action

    logs = crud.get_audit_logs(db, filters if filters else None, limit)
    result = []
    for log in logs:
        user = crud.get_user_by_id(db, log.user_id) if log.user_id else None
        result.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_name": user.full_name if user else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": log.created_at
        })
    return result


# ======================
# ADMIN: Reports & Export
# ======================
@app.get("/admin/reports/students")
def admin_report_students(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if status:
        filters["status"] = status
    if search:
        filters["search"] = search

    students = crud.get_students_report(db, filters if filters else None)
    return students

@app.get("/admin/reports/invoices")
def admin_report_invoices(
    status: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if status:
        filters["status"] = status
    if student_id:
        filters["student_id"] = student_id
    if start_date:
        filters["start_date"] = start_date
    if end_date:
        filters["end_date"] = end_date

    invoices = crud.get_invoices_report(db, filters if filters else None)
    result = []
    for inv in invoices:
        student = crud.get_student_by_id(db, inv.student_id)
        result.append({
            "id": inv.id,
            "student_id": inv.student_id,
            "student_name": student.full_name if student else None,
            "period": inv.period,
            "amount": float(inv.amount),
            "status": inv.status,
            "payment_url": inv.payment_url,
            "paid_at": inv.paid_at
        })
    return result

@app.get("/admin/reports/procedures")
def admin_report_procedures(
    status: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    assigned_to: Optional[int] = Query(None),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if status:
        filters["status"] = status
    if student_id:
        filters["student_id"] = student_id
    if assigned_to:
        filters["assigned_to"] = assigned_to

    procedures = crud.get_all_procedures(db, filters if filters else None)
    return [_format_procedure(db, p) for p in procedures]


# ======================
# CSV Export
# ======================
@app.get("/admin/export/students")
def export_students_csv(
    status: Optional[str] = Query(None),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {"status": status} if status else None
    students = crud.get_students_report(db, filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nombre Completo", "Email Google", "Estado", "Fecha Creación"])

    for s in students:
        writer.writerow([s.id, s.full_name, s.google_email or "", s.status, s.created_at.strftime("%Y-%m-%d %H:%M")])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alumnos.csv"}
    )

@app.get("/admin/export/invoices")
def export_invoices_csv(
    status: Optional[str] = Query(None),
    student_id: Optional[int] = Query(None),
    _ctx = Depends(require_permission("invoices:read")),
    db: Session = Depends(get_db)
):
    filters = {}
    if status:
        filters["status"] = status
    if student_id:
        filters["student_id"] = student_id

    invoices = crud.get_invoices_report(db, filters if filters else None)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Alumno ID", "Alumno", "Periodo", "Monto", "Estado", "Fecha Pago"])

    for inv in invoices:
        student = crud.get_student_by_id(db, inv.student_id)
        writer.writerow([
            inv.id,
            inv.student_id,
            student.full_name if student else "",
            inv.period.strftime("%Y-%m"),
            float(inv.amount),
            inv.status,
            inv.paid_at.strftime("%Y-%m-%d %H:%M") if inv.paid_at else ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mensualidades.csv"}
    )

@app.get("/admin/export/procedures")
def export_procedures_csv(
    status: Optional[str] = Query(None),
    _ctx = Depends(require_permission("students:read")),
    db: Session = Depends(get_db)
):
    filters = {"status": status} if status else None
    procedures = crud.get_all_procedures(db, filters)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Alumno", "Tipo", "Estado", "Solicitado Por", "Asignado A", "Fecha Creación"])

    for p in procedures:
        student = crud.get_student_by_id(db, p.student_id)
        requested_by = crud.get_user_by_id(db, p.requested_by) if p.requested_by else None
        assigned_to = crud.get_user_by_id(db, p.assigned_to) if p.assigned_to else None
        writer.writerow([
            p.id,
            student.full_name if student else "",
            p.procedure_type,
            p.status,
            requested_by.full_name if requested_by else "",
            assigned_to.full_name if assigned_to else "",
            p.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tramites.csv"}
    )
