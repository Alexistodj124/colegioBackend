-- =========================
--  ESQUEMA COMPLETO (MVP)
--  PostgreSQL - Portal Educativo
--  Roles: PADRE | MAESTRO | ADMIN
--  Pagos: SOLO link externo + control PAGADO/PENDIENTE
-- =========================

-- (Opcional) usar un schema dedicado
-- create schema if not exists edu;
-- set search_path to edu;

-- ====== Limpieza (opcional) ======
-- DROP TABLE IF EXISTS teacher_students CASCADE;
-- DROP TABLE IF EXISTS parent_students CASCADE;
-- DROP TABLE IF EXISTS monthly_invoices CASCADE;
-- DROP TABLE IF EXISTS students CASCADE;
-- DROP TABLE IF EXISTS role_permissions CASCADE;
-- DROP TABLE IF EXISTS user_roles CASCADE;
-- DROP TABLE IF EXISTS permissions CASCADE;
-- DROP TABLE IF EXISTS roles CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;
-- DROP TYPE  IF EXISTS student_status;
-- DROP TYPE  IF EXISTS payment_status;
-- DROP TYPE  IF EXISTS procedure_status;

-- ====== Tipos ======
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'student_status') THEN
    CREATE TYPE student_status AS ENUM ('VIGENTE','ATRASADO','RETIRADO');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
    CREATE TYPE payment_status AS ENUM ('PENDIENTE','PAGADO');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'procedure_status') THEN
    CREATE TYPE procedure_status AS ENUM ('PENDIENTE','EN_PROCESO','APROBADO','RECHAZADO');
  END IF;
END$$;

-- ====== Seguridad ======
CREATE TABLE IF NOT EXISTS roles (
  id   BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE  -- PADRE | MAESTRO | ADMIN
);

CREATE TABLE IF NOT EXISTS permissions (
  id   BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE  -- e.g. students:read, invoices:read, invoices:mark_paid
);

CREATE TABLE IF NOT EXISTS users (
  id            BIGSERIAL PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  full_name     TEXT NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id       BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user   ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_role_perm_role    ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_perm_perm    ON role_permissions(permission_id);

-- ====== Core educativo ======
CREATE TABLE IF NOT EXISTS students (
  id          BIGSERIAL PRIMARY KEY,
  full_name   TEXT NOT NULL,
  google_email TEXT,
  status      student_status NOT NULL DEFAULT 'VIGENTE',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Padre ↔ Hijo(s)
CREATE TABLE IF NOT EXISTS parent_students (
  parent_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  student_id     BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  relationship   TEXT DEFAULT 'Padre/Madre',
  PRIMARY KEY (parent_user_id, student_id)
);

-- Maestro ↔ Alumno(s)
CREATE TABLE IF NOT EXISTS teacher_students (
  teacher_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  student_id      BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  PRIMARY KEY (teacher_user_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_parent_students_parent ON parent_students(parent_user_id);
CREATE INDEX IF NOT EXISTS idx_teacher_students_teacher ON teacher_students(teacher_user_id);

-- ====== Mensualidades (link externo + control pagado/no pagado) ======
-- period: usar el 1er día del mes (ej: 2026-01-01) para identificar el mes
CREATE TABLE IF NOT EXISTS monthly_invoices (
  id                  BIGSERIAL PRIMARY KEY,
  student_id          BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  period              DATE NOT NULL,
  amount              NUMERIC(12,2) NOT NULL,
  status              payment_status NOT NULL DEFAULT 'PENDIENTE',
  payment_url         TEXT NOT NULL,         -- link a la plataforma externa
  external_payment_id TEXT,                  -- opcional (si te lo da la pasarela)
  paid_at             TIMESTAMPTZ,           -- cuando se marcó pagado
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (student_id, period)
);

CREATE INDEX IF NOT EXISTS idx_invoices_student ON monthly_invoices(student_id);
CREATE INDEX IF NOT EXISTS idx_invoices_period  ON monthly_invoices(period);
CREATE INDEX IF NOT EXISTS idx_invoices_status  ON monthly_invoices(status);

-- ====== Trámites ======
CREATE TABLE IF NOT EXISTS procedures (
  id              BIGSERIAL PRIMARY KEY,
  student_id      BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  procedure_type  TEXT NOT NULL,
  description     TEXT,
  status          procedure_status NOT NULL DEFAULT 'PENDIENTE',
  requested_by    BIGINT REFERENCES users(id) ON DELETE SET NULL,
  approved_by     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  approved_at     TIMESTAMPTZ,
  notes           TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_procedures_student ON procedures(student_id);
CREATE INDEX IF NOT EXISTS idx_procedures_status  ON procedures(status);

-- ====== Seeds: Roles + Permisos ======
INSERT INTO roles(name) VALUES ('PADRE')  ON CONFLICT (name) DO NOTHING;
INSERT INTO roles(name) VALUES ('MAESTRO') ON CONFLICT (name) DO NOTHING;
INSERT INTO roles(name) VALUES ('ADMIN')  ON CONFLICT (name) DO NOTHING;

-- Permisos MVP
INSERT INTO permissions(code) VALUES ('students:read')         ON CONFLICT (code) DO NOTHING;
INSERT INTO permissions(code) VALUES ('invoices:read')         ON CONFLICT (code) DO NOTHING;
INSERT INTO permissions(code) VALUES ('invoices:mark_paid')    ON CONFLICT (code) DO NOTHING;
INSERT INTO permissions(code) VALUES ('teachers:read')         ON CONFLICT (code) DO NOTHING;
INSERT INTO permissions(code) VALUES ('students:assign')       ON CONFLICT (code) DO NOTHING;

-- PADRE: leer sus alumnos + ver sus mensualidades
INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('students:read','invoices:read')
WHERE r.name = 'PADRE'
ON CONFLICT DO NOTHING;

-- MAESTRO: leer alumnos asignados
INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('students:read')
WHERE r.name = 'MAESTRO'
ON CONFLICT DO NOTHING;

-- ADMIN: ver todo + marcar pagado + asignaciones
INSERT INTO role_permissions(role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN ('students:read','invoices:read','invoices:mark_paid','teachers:read','students:assign')
WHERE r.name = 'ADMIN'
ON CONFLICT DO NOTHING;

-- =========================
-- VISTAS ÚTILES (opcionales)
-- =========================

-- 1) Vista: hijos del padre con estado
CREATE OR REPLACE VIEW v_parent_students AS
SELECT
  ps.parent_user_id,
  s.id       AS student_id,
  s.full_name,
  s.status,
  ps.relationship
FROM parent_students ps
JOIN students s ON s.id = ps.student_id;

-- 2) Vista: mensualidades por alumno
CREATE OR REPLACE VIEW v_student_invoices AS
SELECT
  mi.id AS invoice_id,
  mi.student_id,
  s.full_name AS student_name,
  mi.period,
  mi.amount,
  mi.status,
  mi.payment_url,
  mi.external_payment_id,
  mi.paid_at,
  mi.created_at
FROM monthly_invoices mi
JOIN students s ON s.id = mi.student_id;
