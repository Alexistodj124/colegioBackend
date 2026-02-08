"""
Configuracion global de tests.
Usa SQLite in-memory para no depender de PostgreSQL.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test_secret_key_for_tests"

# Patches para compatibilidad SQLite (deben ir ANTES de importar modelos)
from sqlalchemy import BigInteger
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM


@compiles(PG_ENUM, "sqlite")
def _compile_enum_sqlite(element, compiler, **kw):
    return "TEXT"


@compiles(BigInteger, "sqlite")
def _compile_bigint_sqlite(element, compiler, **kw):
    return "INTEGER"


import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db import Base
from main import app
from deps import get_db
from security import get_password_hash
from models import (
    Role, Permission, RolePermission, User, UserRole,
    Student, ParentStudent, TeacherStudent, MonthlyInvoice, Procedure, Program,
)

# ---------------------------------------------------------------------------
# Engine & Session de prueba
# ---------------------------------------------------------------------------
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def _enable_fk(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

# ---------------------------------------------------------------------------
# Crear tablas + seed de roles/permisos (una vez por sesion de pytest)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    Base.metadata.create_all(bind=test_engine)

    db = TestingSession()
    # Roles
    db.execute(text("INSERT INTO roles (id, name) VALUES (1,'ADMIN'),(2,'PADRE'),(3,'MAESTRO')"))
    # Permisos
    db.execute(text(
        "INSERT INTO permissions (id, code) VALUES "
        "(1,'students:read'),(2,'invoices:read'),(3,'invoices:mark_paid'),"
        "(4,'teachers:read'),(5,'students:assign')"
    ))
    # ADMIN -> todos los permisos
    db.execute(text(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES "
        "(1,1),(1,2),(1,3),(1,4),(1,5)"
    ))
    # PADRE -> students:read, invoices:read
    db.execute(text(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES (2,1),(2,2)"
    ))
    # MAESTRO -> students:read, teachers:read
    db.execute(text(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES (3,1),(3,4)"
    ))
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


# ---------------------------------------------------------------------------
# Limpiar datos entre cada test (mantiene roles/permisos)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_data():
    yield  # test corre aqui
    db = TestingSession()
    for tbl in (
        "audit_logs", "student_programs", "procedures",
        "monthly_invoices", "parent_students", "teacher_students",
        "programs", "students", "user_roles", "users",
    ):
        db.execute(text(f"DELETE FROM {tbl}"))
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = TestingSession()
    yield session
    session.close()


# --- Helpers de creacion ---------------------------------------------------

def make_user(db_session, email, password, full_name, role_name):
    """Crea un usuario con rol y devuelve el objeto User."""
    user = User(
        email=email,
        password_hash=get_password_hash(password),
        full_name=full_name,
    )
    db_session.add(user)
    db_session.flush()

    role = db_session.execute(select(Role).where(Role.name == role_name)).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    db_session.refresh(user)
    return user


def make_student(db_session, full_name="Alumno Test", google_email="alumno@google.com",
                 status="VIGENTE"):
    s = Student(full_name=full_name, google_email=google_email, status=status)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def link_parent(db_session, parent_id, student_id, relationship="Padre/Madre"):
    ps = ParentStudent(parent_user_id=parent_id, student_id=student_id, relationship=relationship)
    db_session.add(ps)
    db_session.commit()


def make_invoice(db_session, student_id, period=None, amount=500.00):
    inv = MonthlyInvoice(
        student_id=student_id,
        period=period or date(2025, 1, 1),
        amount=amount,
        payment_url="https://test.com/pay",
        status="PENDIENTE",
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def make_procedure(db_session, student_id, requested_by,
                   procedure_type="CONSTANCIA_ESTUDIOS", assigned_to=None):
    proc = Procedure(
        student_id=student_id,
        procedure_type=procedure_type,
        status="PENDIENTE",
        requested_by=requested_by,
        assigned_to=assigned_to,
    )
    db_session.add(proc)
    db_session.commit()
    db_session.refresh(proc)
    return proc


def make_program(db_session, name="Programa Test"):
    prog = Program(name=name, description="desc")
    db_session.add(prog)
    db_session.commit()
    db_session.refresh(prog)
    return prog


# --- Fixtures de usuarios -------------------------------------------------

@pytest.fixture
def admin_user(db):
    return make_user(db, "admin@test.com", "Admin123!", "Admin User", "ADMIN")


@pytest.fixture
def parent_user(db):
    return make_user(db, "padre@test.com", "Padre123!", "Padre User", "PADRE")


@pytest.fixture
def teacher_user(db):
    return make_user(db, "maestro@test.com", "Maestro123!", "Maestro User", "MAESTRO")


# --- Fixtures de tokens ---------------------------------------------------

def get_token(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()["access_token"]


@pytest.fixture
def admin_token(client, admin_user):
    return get_token(client, "admin@test.com", "Admin123!")


@pytest.fixture
def parent_token(client, parent_user):
    return get_token(client, "padre@test.com", "Padre123!")


@pytest.fixture
def teacher_token(client, teacher_user):
    return get_token(client, "maestro@test.com", "Maestro123!")


def auth(token):
    """Retorna header Authorization."""
    return {"Authorization": f"Bearer {token}"}
