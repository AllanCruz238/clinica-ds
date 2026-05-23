import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_clinica.settings")
django.setup()

from django.db import connection
from django.contrib.auth.hashers import make_password


ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Administrador")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@nubnest.com")


with connection.cursor() as cursor:
    cursor.execute("""
        INSERT INTO roles (descripcion, activo)
        SELECT 'Administrador', TRUE
        WHERE NOT EXISTS (
            SELECT 1 FROM roles WHERE descripcion = 'Administrador'
        );
    """)

    cursor.execute("""
        SELECT id_rol FROM roles
        WHERE descripcion = 'Administrador'
        LIMIT 1;
    """)
    rol = cursor.fetchone()

    if not rol:
        raise Exception("No se pudo crear o encontrar el rol Administrador")

    id_rol = rol[0]
    password_hash = make_password(ADMIN_PASSWORD)

    cursor.execute("""
        INSERT INTO usuarios (
            usuario,
            password_hash,
            nombre,
            correo,
            telefono,
            id_rol,
            activo,
            fecha_creacion
        )
        SELECT %s, %s, %s, %s, %s, %s, TRUE, NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM usuarios WHERE usuario = %s
        );
    """, [
        ADMIN_USER,
        password_hash,
        ADMIN_NAME,
        ADMIN_EMAIL,
        '00000000',
        id_rol,
        ADMIN_USER
    ])

print("Usuario administrador verificado/creado correctamente.")