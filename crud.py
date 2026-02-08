from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timezone, date
from typing import Optional
from models import (
    User, Role, Permission, UserRole, RolePermission,
    ParentStudent, Student, MonthlyInvoice, Procedure,
    Program, StudentProgram, AuditLog
)
from security import get_password_hash

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

def get_roles_and_permissions(db: Session, user_id: int) -> tuple[list[str], list[str]]:
    roles = db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    ).scalars().all()

    perms = db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
        .distinct()
    ).scalars().all()

    return list(roles), list(perms)

def parent_get_students(db: Session, parent_user_id: int):
    rows = db.execute(
        select(
            Student.id.label("student_id"),
            Student.full_name,
            Student.status,
            ParentStudent.relationship
        )
        .join(ParentStudent, ParentStudent.student_id == Student.id)
        .where(ParentStudent.parent_user_id == parent_user_id)
        .order_by(Student.full_name.asc())
    ).all()
    return rows

def parent_student_belongs(db: Session, parent_user_id: int, student_id: int) -> bool:
    r = db.execute(
        select(ParentStudent.student_id)
        .where(ParentStudent.parent_user_id == parent_user_id, ParentStudent.student_id == student_id)
    ).first()
    return r is not None

def parent_get_invoices(db: Session, student_id: int):
    rows = db.execute(
        select(
            MonthlyInvoice.id,
            MonthlyInvoice.student_id,
            MonthlyInvoice.period,
            MonthlyInvoice.amount,
            MonthlyInvoice.status,
            MonthlyInvoice.payment_url,
            MonthlyInvoice.paid_at
        )
        .where(MonthlyInvoice.student_id == student_id)
        .order_by(MonthlyInvoice.period.desc())
    ).all()
    return rows

def admin_mark_invoice_paid(db: Session, invoice_id: int, external_payment_id: Optional[str]):
    inv = db.execute(select(MonthlyInvoice).where(MonthlyInvoice.id == invoice_id)).scalar_one_or_none()
    if not inv:
        return None

    inv.status = "PAGADO"
    inv.external_payment_id = external_payment_id or inv.external_payment_id
    inv.paid_at = datetime.now(timezone.utc)

    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv

# ========== Students CRUD ==========
def get_all_students(db: Session):
    rows = db.execute(
        select(Student)
        .order_by(Student.created_at.desc())
    ).scalars().all()
    return rows

def get_student_by_id(db: Session, student_id: int):
    return db.execute(select(Student).where(Student.id == student_id)).scalar_one_or_none()

def create_student(db: Session, full_name: str, google_email: Optional[str], status: str = "VIGENTE"):
    student = Student(
        full_name=full_name,
        google_email=google_email,
        status=status
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student

def update_student(db: Session, student_id: int, full_name: Optional[str] = None,
                  google_email: Optional[str] = None, status: Optional[str] = None):
    student = get_student_by_id(db, student_id)
    if not student:
        return None

    if full_name is not None:
        student.full_name = full_name
    if google_email is not None:
        student.google_email = google_email
    if status is not None:
        student.status = status

    db.add(student)
    db.commit()
    db.refresh(student)
    return student

def delete_student(db: Session, student_id: int):
    student = get_student_by_id(db, student_id)
    if not student:
        return False

    db.delete(student)
    db.commit()
    return True

# ========== Procedures CRUD ==========
def get_all_procedures(db: Session, filters: dict = None):
    query = select(Procedure).order_by(Procedure.created_at.desc())

    if filters:
        if filters.get("status"):
            query = query.where(Procedure.status == filters["status"])
        if filters.get("student_id"):
            query = query.where(Procedure.student_id == filters["student_id"])
        if filters.get("assigned_to"):
            query = query.where(Procedure.assigned_to == filters["assigned_to"])
        if filters.get("start_date"):
            query = query.where(Procedure.created_at >= filters["start_date"])
        if filters.get("end_date"):
            query = query.where(Procedure.created_at <= filters["end_date"])

    rows = db.execute(query).scalars().all()
    return rows

def get_procedures_by_student(db: Session, student_id: int):
    rows = db.execute(
        select(Procedure)
        .where(Procedure.student_id == student_id)
        .order_by(Procedure.created_at.desc())
    ).scalars().all()
    return rows

def get_procedure_by_id(db: Session, procedure_id: int):
    return db.execute(select(Procedure).where(Procedure.id == procedure_id)).scalar_one_or_none()

def create_procedure(db: Session, student_id: int, procedure_type: str,
                    description: Optional[str], requested_by: int):
    procedure = Procedure(
        student_id=student_id,
        procedure_type=procedure_type,
        description=description,
        status="PENDIENTE",
        requested_by=requested_by
    )
    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    return procedure

def update_procedure(db: Session, procedure_id: int, status: Optional[str] = None,
                    notes: Optional[str] = None, approved_by: Optional[int] = None,
                    assigned_to: Optional[int] = None):
    procedure = get_procedure_by_id(db, procedure_id)
    if not procedure:
        return None

    if status is not None:
        procedure.status = status
        if status in ["APROBADO", "RECHAZADO"]:
            procedure.approved_at = datetime.now(timezone.utc)
            if approved_by:
                procedure.approved_by = approved_by

    if notes is not None:
        procedure.notes = notes

    if assigned_to is not None:
        procedure.assigned_to = assigned_to

    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    return procedure

def delete_procedure(db: Session, procedure_id: int):
    procedure = get_procedure_by_id(db, procedure_id)
    if not procedure:
        return False

    db.delete(procedure)
    db.commit()
    return True

# ========== Invoices CRUD ==========
def get_all_invoices(db: Session):
    rows = db.execute(
        select(MonthlyInvoice)
        .order_by(MonthlyInvoice.period.desc())
    ).scalars().all()
    return rows

def get_invoice_by_id(db: Session, invoice_id: int):
    return db.execute(select(MonthlyInvoice).where(MonthlyInvoice.id == invoice_id)).scalar_one_or_none()

def create_invoice(db: Session, student_id: int, period, amount: float, payment_url: str):
    invoice = MonthlyInvoice(
        student_id=student_id,
        period=period,
        amount=amount,
        payment_url=payment_url,
        status="PENDIENTE"
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

def update_invoice(db: Session, invoice_id: int, status: Optional[str] = None,
                  payment_url: Optional[str] = None):
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        return None

    if status is not None:
        invoice.status = status
        if status == "PAGADO":
            invoice.paid_at = datetime.now(timezone.utc)

    if payment_url is not None:
        invoice.payment_url = payment_url

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice

def delete_invoice(db: Session, invoice_id: int):
    invoice = get_invoice_by_id(db, invoice_id)
    if not invoice:
        return False

    db.delete(invoice)
    db.commit()
    return True

# ========== Dashboard Stats ==========
def get_dashboard_stats(db: Session):
    total_students = db.execute(select(func.count(Student.id))).scalar()
    active_students = db.execute(
        select(func.count(Student.id)).where(Student.status == "VIGENTE")
    ).scalar()
    late_students = db.execute(
        select(func.count(Student.id)).where(Student.status == "ATRASADO")
    ).scalar()
    withdrawn_students = db.execute(
        select(func.count(Student.id)).where(Student.status == "RETIRADO")
    ).scalar()

    pending_invoices = db.execute(
        select(func.count(MonthlyInvoice.id)).where(MonthlyInvoice.status == "PENDIENTE")
    ).scalar()
    paid_invoices = db.execute(
        select(func.count(MonthlyInvoice.id)).where(MonthlyInvoice.status == "PAGADO")
    ).scalar()

    pending_procedures = db.execute(
        select(func.count(Procedure.id)).where(Procedure.status.in_(["PENDIENTE", "EN_PROCESO"]))
    ).scalar()
    approved_procedures = db.execute(
        select(func.count(Procedure.id)).where(Procedure.status == "APROBADO")
    ).scalar()

    # Trámites sin asignar (requieren atención del admin)
    unassigned_procedures = db.execute(
        select(func.count(Procedure.id)).where(
            and_(
                Procedure.status.in_(["PENDIENTE", "EN_PROCESO"]),
                Procedure.assigned_to == None
            )
        )
    ).scalar()

    return {
        "total_students": total_students or 0,
        "active_students": active_students or 0,
        "late_students": late_students or 0,
        "withdrawn_students": withdrawn_students or 0,
        "pending_invoices": pending_invoices or 0,
        "paid_invoices": paid_invoices or 0,
        "pending_procedures": pending_procedures or 0,
        "approved_procedures": approved_procedures or 0,
        "unassigned_procedures": unassigned_procedures or 0
    }


# ========== Programs CRUD ==========
def get_all_programs(db: Session):
    rows = db.execute(
        select(Program)
        .order_by(Program.created_at.desc())
    ).scalars().all()
    return rows

def get_program_by_id(db: Session, program_id: int):
    return db.execute(select(Program).where(Program.id == program_id)).scalar_one_or_none()

def create_program(db: Session, name: str, description: Optional[str] = None,
                  google_classroom_id: Optional[str] = None, google_classroom_link: Optional[str] = None):
    program = Program(
        name=name,
        description=description,
        google_classroom_id=google_classroom_id,
        google_classroom_link=google_classroom_link
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    return program

def update_program(db: Session, program_id: int, name: Optional[str] = None,
                  description: Optional[str] = None, google_classroom_id: Optional[str] = None,
                  google_classroom_link: Optional[str] = None, is_active: Optional[bool] = None):
    program = get_program_by_id(db, program_id)
    if not program:
        return None

    if name is not None:
        program.name = name
    if description is not None:
        program.description = description
    if google_classroom_id is not None:
        program.google_classroom_id = google_classroom_id
    if google_classroom_link is not None:
        program.google_classroom_link = google_classroom_link
    if is_active is not None:
        program.is_active = is_active

    db.add(program)
    db.commit()
    db.refresh(program)
    return program

def delete_program(db: Session, program_id: int):
    program = get_program_by_id(db, program_id)
    if not program:
        return False

    db.delete(program)
    db.commit()
    return True


# ========== Users CRUD ==========
def get_all_users(db: Session):
    rows = db.execute(
        select(User)
        .order_by(User.created_at.desc())
    ).scalars().all()
    return rows

def get_users_by_role(db: Session, role_name: str):
    rows = db.execute(
        select(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(Role.name == role_name)
        .order_by(User.full_name.asc())
    ).scalars().all()
    return rows

def create_user(db: Session, email: str, password: str, full_name: str, role_names: list[str] = None):
    user = User(
        email=email.lower().strip(),
        password_hash=get_password_hash(password),
        full_name=full_name.strip()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if role_names:
        for role_name in role_names:
            role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                db.add(user_role)
        db.commit()

    return user

def update_user(db: Session, user_id: int, email: Optional[str] = None,
               password: Optional[str] = None, full_name: Optional[str] = None,
               is_active: Optional[bool] = None, role_names: Optional[list[str]] = None):
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    if email is not None:
        user.email = email.lower().strip()
    if password is not None:
        user.password_hash = get_password_hash(password)
    if full_name is not None:
        user.full_name = full_name.strip()
    if is_active is not None:
        user.is_active = is_active

    if role_names is not None:
        # Eliminar roles existentes
        existing_roles = db.execute(select(UserRole).where(UserRole.user_id == user_id)).scalars().all()
        for ur in existing_roles:
            db.delete(ur)

        # Agregar nuevos roles
        for role_name in role_names:
            role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
            if role:
                user_role = UserRole(user_id=user.id, role_id=role.id)
                db.add(user_role)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    db.delete(user)
    db.commit()
    return True

def get_all_roles(db: Session):
    rows = db.execute(select(Role).order_by(Role.name.asc())).scalars().all()
    return rows


# ========== Audit Log ==========
def create_audit_log(db: Session, user_id: Optional[int], action: str, entity_type: str,
                    entity_id: Optional[int] = None, details: Optional[str] = None,
                    ip_address: Optional[str] = None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
    return log

def get_audit_logs(db: Session, filters: dict = None, limit: int = 100):
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)

    if filters:
        if filters.get("user_id"):
            query = query.where(AuditLog.user_id == filters["user_id"])
        if filters.get("entity_type"):
            query = query.where(AuditLog.entity_type == filters["entity_type"])
        if filters.get("action"):
            query = query.where(AuditLog.action == filters["action"])
        if filters.get("start_date"):
            query = query.where(AuditLog.created_at >= filters["start_date"])
        if filters.get("end_date"):
            query = query.where(AuditLog.created_at <= filters["end_date"])

    rows = db.execute(query).scalars().all()
    return rows


# ========== Reports ==========
def get_invoices_report(db: Session, filters: dict = None):
    query = select(MonthlyInvoice).order_by(MonthlyInvoice.period.desc())

    if filters:
        if filters.get("status"):
            query = query.where(MonthlyInvoice.status == filters["status"])
        if filters.get("student_id"):
            query = query.where(MonthlyInvoice.student_id == filters["student_id"])
        if filters.get("start_date"):
            query = query.where(MonthlyInvoice.period >= filters["start_date"])
        if filters.get("end_date"):
            query = query.where(MonthlyInvoice.period <= filters["end_date"])

    rows = db.execute(query).scalars().all()
    return rows

def get_students_report(db: Session, filters: dict = None):
    query = select(Student).order_by(Student.full_name.asc())

    if filters:
        if filters.get("status"):
            query = query.where(Student.status == filters["status"])
        if filters.get("search"):
            search = f"%{filters['search']}%"
            query = query.where(
                or_(
                    Student.full_name.ilike(search),
                    Student.google_email.ilike(search)
                )
            )

    rows = db.execute(query).scalars().all()
    return rows
