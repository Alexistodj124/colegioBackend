-- =========================
-- USUARIOS
-- password: Admin123!
-- =========================
INSERT INTO users (email, password_hash, full_name)
VALUES
('admin@colegio.com',  '$2b$12$yJH8Vwq2Z0Zc0kqK0v8sSePpZz2M9a4G2Jc7N2ZVZc7JvFJp5m3q2', 'Administrador General'),
('padre@colegio.com',  '$2b$12$yJH8Vwq2Z0Zc0kqK0v8sSePpZz2M9a4G2Jc7N2ZVZc7JvFJp5m3q2', 'Juan Pérez'),
('maestro@colegio.com','$2b$12$yJH8Vwq2Z0Zc0kqK0v8sSePpZz2M9a4G2Jc7N2ZVZc7JvFJp5m3q2', 'María López')
ON CONFLICT (email) DO NOTHING;

-- =========================
-- ASIGNAR ROLES
-- =========================
-- ADMIN
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'admin@colegio.com' AND r.name = 'ADMIN'
ON CONFLICT DO NOTHING;

-- PADRE
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'padre@colegio.com' AND r.name = 'PADRE'
ON CONFLICT DO NOTHING;

-- MAESTRO
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u, roles r
WHERE u.email = 'maestro@colegio.com' AND r.name = 'MAESTRO'
ON CONFLICT DO NOTHING;

-- =========================
-- ALUMNOS
-- =========================
INSERT INTO students (full_name, google_email, status)
VALUES
('Carlos Pérez', 'carlos.perez@colegio.com', 'VIGENTE'),
('Ana Pérez',    'ana.perez@colegio.com',    'ATRASADO')
ON CONFLICT DO NOTHING;

-- =========================
-- PADRE ↔ HIJOS
-- =========================
INSERT INTO parent_students (parent_user_id, student_id)
SELECT u.id, s.id
FROM users u, students s
WHERE u.email = 'padre@colegio.com'
  AND s.full_name IN ('Carlos Pérez','Ana Pérez')
ON CONFLICT DO NOTHING;

-- =========================
-- MAESTRO ↔ ALUMNOS
-- =========================
INSERT INTO teacher_students (teacher_user_id, student_id)
SELECT u.id, s.id
FROM users u, students s
WHERE u.email = 'maestro@colegio.com'
  AND s.full_name IN ('Carlos Pérez','Ana Pérez')
ON CONFLICT DO NOTHING;

-- =========================
-- MENSUALIDADES (LINK EXTERNO)
-- =========================
-- Enero 2026
INSERT INTO monthly_invoices
(student_id, period, amount, payment_url)
SELECT
  s.id,
  DATE '2026-01-01',
  750.00,
  'https://pagos.plataformaexterna.com/pay?alumno=' || s.id || '&mes=2026-01'
FROM students s
WHERE s.full_name IN ('Carlos Pérez','Ana Pérez')
ON CONFLICT DO NOTHING;

-- Febrero 2026
INSERT INTO monthly_invoices
(student_id, period, amount, payment_url)
SELECT
  s.id,
  DATE '2026-02-01',
  750.00,
  'https://pagos.plataformaexterna.com/pay?alumno=' || s.id || '&mes=2026-02'
FROM students s
WHERE s.full_name IN ('Carlos Pérez','Ana Pérez')
ON CONFLICT DO NOTHING;
