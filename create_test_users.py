"""
Script para crear usuarios de prueba con diferentes roles.

Ejecutar desde el directorio backend:
python create_test_users.py
"""

import sys
import io

# Fix encoding para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlalchemy.orm import Session
from db import engine, SessionLocal
from models import User, Role, UserRole
from security import hash_password

def create_test_users():
    db: Session = SessionLocal()

    try:
        # Verificar que existan los roles
        roles = {
            "PADRE": db.query(Role).filter(Role.name == "PADRE").first(),
            "MAESTRO": db.query(Role).filter(Role.name == "MAESTRO").first(),
            "ADMIN": db.query(Role).filter(Role.name == "ADMIN").first(),
        }

        if not all(roles.values()):
            print("Error: No se encontraron todos los roles necesarios.")
            print("Asegúrate de que los roles PADRE, MAESTRO y ADMIN existan en la tabla roles.")
            return

        # Lista de usuarios de prueba
        test_users = [
            {
                "email": "padre@colegio.com",
                "password": "Admin123!",
                "full_name": "Juan Pérez",
                "role": "PADRE"
            },
            {
                "email": "maestro@colegio.com",
                "password": "Admin123!",
                "full_name": "María García",
                "role": "MAESTRO"
            },
            {
                "email": "admin@colegio.com",
                "password": "Admin123!",
                "full_name": "Carlos Admin",
                "role": "ADMIN"
            }
        ]

        print("Creando usuarios de prueba...")
        print("-" * 60)

        for user_data in test_users:
            # Verificar si el usuario ya existe
            existing_user = db.query(User).filter(User.email == user_data["email"]).first()

            if existing_user:
                print(f"✓ Usuario {user_data['email']} ya existe")
                # Actualizar la contraseña si ya existe
                existing_user.password_hash = hash_password(user_data["password"])
                existing_user.full_name = user_data["full_name"]
                db.commit()
                print(f"  → Contraseña actualizada para {user_data['email']}")
            else:
                # Crear nuevo usuario
                new_user = User(
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    full_name=user_data["full_name"],
                    is_active=True
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)

                # Asignar rol
                role = roles[user_data["role"]]
                user_role = UserRole(user_id=new_user.id, role_id=role.id)
                db.add(user_role)
                db.commit()

                print(f"✓ Usuario creado: {user_data['email']}")
                print(f"  → Nombre: {user_data['full_name']}")
                print(f"  → Rol: {user_data['role']}")
                print(f"  → Contraseña: {user_data['password']}")

        print("-" * 60)
        print("\n✅ Usuarios de prueba creados exitosamente!")
        print("\nCredenciales de acceso:")
        print("-" * 60)
        for user_data in test_users:
            print(f"\n{user_data['role']}:")
            print(f"  Email: {user_data['email']}")
            print(f"  Contraseña: {user_data['password']}")
        print("-" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_test_users()
