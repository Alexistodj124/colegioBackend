from sqlalchemy import (
    Column, BigInteger, Text, Boolean, DateTime, Date, Numeric,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.sql import func
from db import Base

student_status_enum = ENUM("VIGENTE", "ATRASADO", "RETIRADO", name="student_status", create_type=False)
payment_status_enum = ENUM("PENDIENTE", "PAGADO", name="payment_status", create_type=False)
procedure_status_enum = ENUM("PENDIENTE", "EN_PROCESO", "APROBADO", "RECHAZADO", name="procedure_status", create_type=False)

# Catálogo de tipos de trámite predefinidos
# requires_teacher: True = requiere asignación a maestro, False = solo administrativo
PROCEDURE_TYPES = [
    {"code": "CONSTANCIA_ESTUDIOS", "name": "Constancia de Estudios", "description": "Documento que certifica que el alumno está inscrito y activo", "requires_teacher": False},
    {"code": "CONSTANCIA_NOTAS", "name": "Constancia de Notas", "description": "Documento con el historial de calificaciones del alumno", "requires_teacher": True},
    {"code": "SOLVENCIA", "name": "Solvencia", "description": "Documento que certifica que el alumno está al día en sus pagos", "requires_teacher": False},
    {"code": "CARTA_BUENA_CONDUCTA", "name": "Carta de Buena Conducta", "description": "Documento que certifica el buen comportamiento del alumno", "requires_teacher": True},
    {"code": "CERTIFICADO_ESTUDIOS", "name": "Certificado de Estudios", "description": "Documento oficial de estudios completados", "requires_teacher": True},
    {"code": "RETIRO", "name": "Solicitud de Retiro", "description": "Trámite para el retiro formal del alumno", "requires_teacher": False},
    {"code": "OTRO", "name": "Otro", "description": "Otro tipo de trámite no especificado", "requires_teacher": False},
]

class Role(Base):
    __tablename__ = "roles"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text, unique=True, nullable=False)

class Permission(Base):
    __tablename__ = "permissions"
    id = Column(BigInteger, primary_key=True)
    code = Column(Text, unique=True, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    full_name = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column(BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

class Student(Base):
    __tablename__ = "students"
    id = Column(BigInteger, primary_key=True)
    full_name = Column(Text, nullable=False)
    google_email = Column(Text)
    status = Column(student_status_enum, nullable=False, server_default="VIGENTE")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class ParentStudent(Base):
    __tablename__ = "parent_students"
    parent_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column(BigInteger, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    relationship = Column(Text, server_default="Padre/Madre")

class TeacherStudent(Base):
    __tablename__ = "teacher_students"
    teacher_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column(BigInteger, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)

class MonthlyInvoice(Base):
    __tablename__ = "monthly_invoices"
    __table_args__ = (UniqueConstraint("student_id", "period", name="uq_invoice_student_period"),)

    id = Column(BigInteger, primary_key=True)
    student_id = Column(BigInteger, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    period = Column(Date, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(payment_status_enum, nullable=False, server_default="PENDIENTE")

    payment_url = Column(Text, nullable=False)
    external_payment_id = Column(Text)
    paid_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class Procedure(Base):
    __tablename__ = "procedures"

    id = Column(BigInteger, primary_key=True)
    student_id = Column(BigInteger, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    procedure_type = Column(Text, nullable=False)
    description = Column(Text)
    status = Column(procedure_status_enum, nullable=False, server_default="PENDIENTE")
    requested_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    assigned_to = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    approved_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    approved_at = Column(DateTime(timezone=True))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Program(Base):
    """Programas/Cursos con referencia a Google Classroom"""
    __tablename__ = "programs"

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text)
    google_classroom_id = Column(Text)
    google_classroom_link = Column(Text)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StudentProgram(Base):
    """Relación alumno-programa"""
    __tablename__ = "student_programs"
    student_id = Column(BigInteger, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    program_id = Column(BigInteger, ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True)
    enrolled_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditLog(Base):
    """Registro de auditoría para acciones clave"""
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(BigInteger)
    details = Column(Text)
    ip_address = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
