"""
Script de migración para Sprint 3
Ejecutar una sola vez para agregar las nuevas columnas y tablas
"""
from db import engine
from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        # 1. Agregar columna assigned_to a procedures
        print("Agregando columna assigned_to a procedures...")
        try:
            conn.execute(text("""
                ALTER TABLE procedures
                ADD COLUMN IF NOT EXISTS assigned_to BIGINT REFERENCES users(id) ON DELETE SET NULL
            """))
            conn.commit()
            print("  - Columna assigned_to agregada correctamente")
        except Exception as e:
            print(f"  - Error o ya existe: {e}")
            conn.rollback()

        # 2. Crear tabla programs
        print("Creando tabla programs...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS programs (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    google_classroom_id TEXT,
                    google_classroom_link TEXT,
                    is_active BOOLEAN NOT NULL DEFAULT true,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))
            conn.commit()
            print("  - Tabla programs creada correctamente")
        except Exception as e:
            print(f"  - Error: {e}")
            conn.rollback()

        # 3. Crear tabla student_programs
        print("Creando tabla student_programs...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS student_programs (
                    student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,
                    program_id BIGINT REFERENCES programs(id) ON DELETE CASCADE,
                    enrolled_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (student_id, program_id)
                )
            """))
            conn.commit()
            print("  - Tabla student_programs creada correctamente")
        except Exception as e:
            print(f"  - Error: {e}")
            conn.rollback()

        # 4. Crear tabla audit_logs
        print("Creando tabla audit_logs...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                    action TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id BIGINT,
                    details TEXT,
                    ip_address TEXT,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
            """))
            conn.commit()
            print("  - Tabla audit_logs creada correctamente")
        except Exception as e:
            print(f"  - Error: {e}")
            conn.rollback()

        # 5. Crear índices para audit_logs
        print("Creando índices para audit_logs...")
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_type ON audit_logs(entity_type);
                CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
            """))
            conn.commit()
            print("  - Índices creados correctamente")
        except Exception as e:
            print(f"  - Error: {e}")
            conn.rollback()

        print("\n¡Migración completada!")

if __name__ == "__main__":
    run_migration()
