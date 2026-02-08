from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    roles: List[str]
    permissions: List[str]

class MeResponse(BaseModel):
    user: dict
    roles: List[str]
    permissions: List[str]

class StudentOut(BaseModel):
    student_id: int
    full_name: str
    status: str
    relationship: Optional[str] = None

class InvoiceOut(BaseModel):
    id: int
    student_id: int
    period: date
    amount: float
    status: str
    payment_url: str
    paid_at: Optional[datetime] = None

class MarkPaidRequest(BaseModel):
    external_payment_id: Optional[str] = None

# ========== Students CRUD ==========
class StudentCreate(BaseModel):
    full_name: str
    google_email: Optional[str] = None
    status: Optional[str] = "VIGENTE"

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    google_email: Optional[str] = None
    status: Optional[str] = None

class StudentDetail(BaseModel):
    id: int
    full_name: str
    google_email: Optional[str] = None
    status: str
    created_at: datetime

# ========== Procedures CRUD ==========
class ProcedureCreate(BaseModel):
    student_id: int
    procedure_type: str
    description: Optional[str] = None

class ProcedureUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_to: Optional[int] = None

class ProcedureOut(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    procedure_type: str
    description: Optional[str] = None
    status: str
    requested_by: Optional[int] = None
    requested_by_name: Optional[str] = None
    assigned_to: Optional[int] = None
    assigned_to_name: Optional[str] = None
    approved_by: Optional[int] = None
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class ProcedureTypeOut(BaseModel):
    code: str
    name: str
    description: str
    requires_teacher: bool = False  # Indica si el trámite requiere asignación a maestro

# ========== Invoices CRUD ==========
class InvoiceCreate(BaseModel):
    student_id: int
    period: date
    amount: float
    payment_url: Optional[str] = None  # Opcional - se usa link genérico si no se proporciona

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    payment_url: Optional[str] = None

# ========== Dashboard ==========
class DashboardStats(BaseModel):
    total_students: int
    active_students: int
    late_students: int
    withdrawn_students: int
    pending_invoices: int
    paid_invoices: int
    pending_procedures: int
    approved_procedures: int
    unassigned_procedures: int = 0  # Trámites sin asignar que requieren atención

# ========== Programs CRUD ==========
class ProgramCreate(BaseModel):
    name: str
    description: Optional[str] = None
    google_classroom_id: Optional[str] = None
    google_classroom_link: Optional[str] = None

class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    google_classroom_id: Optional[str] = None
    google_classroom_link: Optional[str] = None
    is_active: Optional[bool] = None

class ProgramOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    google_classroom_id: Optional[str] = None
    google_classroom_link: Optional[str] = None
    is_active: bool
    created_at: datetime

# ========== Users CRUD ==========
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    roles: List[str] = []

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    roles: List[str] = []
    created_at: datetime

# ========== Audit Log ==========
class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime

# ========== Reports ==========
class ReportFilters(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    student_id: Optional[int] = None
