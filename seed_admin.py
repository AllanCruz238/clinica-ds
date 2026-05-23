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


def get_columns(table_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
        """, [table_name])
        return {row[0] for row in cursor.fetchall()}


def pick_column(columns, options):
    for option in options:
        if option in columns:
            return option
    return None


with connection.cursor() as cursor:
    roles_cols = get_columns("roles")
    usuarios_cols = get_columns("usuarios")

    rol_nombre_col = pick_column(roles_cols, ["nombre_rol", "rol", "nombre"])
    rol_desc_col = pick_column(roles_cols, ["descripcion", "description"])
    rol_activo_col = pick_column(roles_cols, ["activo", "estado"])
    rol_id_col = pick_column(roles_cols, ["id_rol", "id"])

    if not rol_nombre_col or not rol_id_col:
        raise Exception(f"No se encontraron columnas válidas en roles. Columnas: {roles_cols}")

    insert_cols = [rol_nombre_col]
    insert_vals = ["Administrador"]

    if rol_desc_col:
        insert_cols.append(rol_desc_col)
        insert_vals.append("Administrador")

    if rol_activo_col:
        insert_cols.append(rol_activo_col)
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    cursor.execute(f"""
        INSERT INTO roles ({col_names})
        SELECT {placeholders}
        WHERE NOT EXISTS (
            SELECT 1 FROM roles WHERE {rol_nombre_col} = %s
        );
    """, insert_vals + ["Administrador"])

    cursor.execute(f"""
        SELECT {rol_id_col}
        FROM roles
        WHERE {rol_nombre_col} = %s
        LIMIT 1;
    """, ["Administrador"])

    rol = cursor.fetchone()

    if not rol:
        raise Exception("No se pudo crear o encontrar el rol Administrador")

    id_rol = rol[0]

    user_col = pick_column(usuarios_cols, ["usuario", "nombre_usuario", "username"])
    pass_col = pick_column(usuarios_cols, ["password_hash", "password", "contrasena"])
    nombre_col = pick_column(usuarios_cols, ["nombre", "nombre_completo"])
    correo_col = pick_column(usuarios_cols, ["correo", "email"])
    telefono_col = pick_column(usuarios_cols, ["telefono", "numero", "celular"])
    activo_col = pick_column(usuarios_cols, ["activo", "estado"])
    fecha_col = pick_column(usuarios_cols, ["fecha_creacion", "creado_en", "created_at"])
    rol_user_col = pick_column(usuarios_cols, ["id_rol", "id_rol_id", "rol_id"])

    if not user_col or not pass_col or not rol_user_col:
        raise Exception(f"No se encontraron columnas válidas en usuarios. Columnas: {usuarios_cols}")

    password_hash = make_password(ADMIN_PASSWORD)

    user_insert_cols = [user_col, pass_col, rol_user_col]
    user_insert_vals = [ADMIN_USER, password_hash, id_rol]

    if nombre_col:
        user_insert_cols.append(nombre_col)
        user_insert_vals.append(ADMIN_NAME)

    if correo_col:
        user_insert_cols.append(correo_col)
        user_insert_vals.append(ADMIN_EMAIL)

    if telefono_col:
        user_insert_cols.append(telefono_col)
        user_insert_vals.append("00000000")

    if activo_col:
        user_insert_cols.append(activo_col)
        user_insert_vals.append(1)

    if fecha_col:
        user_insert_cols.append(fecha_col)
        user_insert_vals.append(None)

    final_cols = ", ".join(user_insert_cols)
    final_placeholders = ", ".join(["%s"] * len(user_insert_vals))

    if fecha_col:
        final_placeholders = final_placeholders.replace("%s", "NOW()", 1) if False else final_placeholders

    if fecha_col:
        fecha_index = user_insert_cols.index(fecha_col)
        placeholder_list = ["%s"] * len(user_insert_vals)
        placeholder_list[fecha_index] = "NOW()"
        final_placeholders = ", ".join(placeholder_list)
        user_insert_vals.pop(fecha_index)

    cursor.execute(f"""
        INSERT INTO usuarios ({final_cols})
        SELECT {final_placeholders}
        WHERE NOT EXISTS (
            SELECT 1 FROM usuarios WHERE {user_col} = %s
        );
    """, user_insert_vals + [ADMIN_USER])

print("Usuario administrador verificado/creado correctamente.")