import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend_clinica.settings")
django.setup()

from django.db import connection


def table_exists(table_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]


def get_columns(table_name):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
        """, [table_name])
        return {row[0] for row in cursor.fetchall()}


def insert_role(nombre, descripcion):
    if not table_exists("roles"):
        print("Tabla roles no existe todavía.")
        return

    cols = get_columns("roles")
    nombre_col = "nombre_rol" if "nombre_rol" in cols else "descripcion"
    desc_col = "descripcion" if "descripcion" in cols else None
    activo_col = "activo" if "activo" in cols else None

    insert_cols = [nombre_col]
    insert_vals = [nombre]

    if desc_col and desc_col != nombre_col:
        insert_cols.append(desc_col)
        insert_vals.append(descripcion)

    if activo_col:
        insert_cols.append(activo_col)
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO roles ({col_names})
            SELECT {placeholders}
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE {nombre_col} = %s
            );
        """, insert_vals + [nombre])


def insert_especialidad(nombre, descripcion):
    if not table_exists("especialidades"):
        print("Tabla especialidades no existe todavía.")
        return

    cols = get_columns("especialidades")
    nombre_col = "nombre_especialidad" if "nombre_especialidad" in cols else None
    if not nombre_col:
        print(f"No se encontró columna de nombre en especialidades: {cols}")
        return

    insert_cols = [nombre_col]
    insert_vals = [nombre]

    if "descripcion" in cols:
        insert_cols.append("descripcion")
        insert_vals.append(descripcion)

    if "activo" in cols:
        insert_cols.append("activo")
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO especialidades ({col_names})
            SELECT {placeholders}
            WHERE NOT EXISTS (
                SELECT 1 FROM especialidades WHERE {nombre_col} = %s
            );
        """, insert_vals + [nombre])


def insert_estado_cita(nombre, color):
    if not table_exists("estados_cita"):
        return

    cols = get_columns("estados_cita")
    if "nombre_estado" not in cols:
        return

    insert_cols = ["nombre_estado"]
    insert_vals = [nombre]

    if "color_hex" in cols:
        insert_cols.append("color_hex")
        insert_vals.append(color)

    if "activo" in cols:
        insert_cols.append("activo")
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO estados_cita ({col_names})
            SELECT {placeholders}
            WHERE NOT EXISTS (
                SELECT 1 FROM estados_cita WHERE nombre_estado = %s
            );
        """, insert_vals + [nombre])


def insert_motivo(nombre, descripcion):
    if not table_exists("motivos_consulta"):
        return

    cols = get_columns("motivos_consulta")
    if "nombre_motivo" not in cols:
        return

    insert_cols = ["nombre_motivo"]
    insert_vals = [nombre]

    if "descripcion" in cols:
        insert_cols.append("descripcion")
        insert_vals.append(descripcion)

    if "activo" in cols:
        insert_cols.append("activo")
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO motivos_consulta ({col_names})
            SELECT {placeholders}
            WHERE NOT EXISTS (
                SELECT 1 FROM motivos_consulta WHERE nombre_motivo = %s
            );
        """, insert_vals + [nombre])


def insert_tipo_pago(nombre):
    if not table_exists("tipos_pago"):
        return

    cols = get_columns("tipos_pago")
    if "nombre_tipo_pago" not in cols:
        return

    insert_cols = ["nombre_tipo_pago"]
    insert_vals = [nombre]

    if "activo" in cols:
        insert_cols.append("activo")
        insert_vals.append(1)

    placeholders = ", ".join(["%s"] * len(insert_vals))
    col_names = ", ".join(insert_cols)

    with connection.cursor() as cursor:
        cursor.execute(f"""
            INSERT INTO tipos_pago ({col_names})
            SELECT {placeholders}
            WHERE NOT EXISTS (
                SELECT 1 FROM tipos_pago WHERE nombre_tipo_pago = %s
            );
        """, insert_vals + [nombre])


def main():
    # Roles principales para el sistema.
    insert_role("Administrador", "Acceso completo al sistema.")
    insert_role("Doctor", "Acceso a módulos clínicos y gestión de sus citas/notas.")
    insert_role("Paciente", "Usuario paciente para acceso limitado o vinculación futura.")

    # Especialidades
    insert_especialidad("Medicina General", "Atención médica general.")
    insert_especialidad("Pediatría", "Atención médica infantil.")
    insert_especialidad("Ginecología y Obstetricia", "Atención ginecológica y obstétrica.")
    insert_especialidad("Cardiología", "Diagnóstico y tratamiento de enfermedades cardíacas.")
    insert_especialidad("Dermatología", "Enfermedades de la piel.")
    insert_especialidad("Neurología", "Trastornos del sistema nervioso.")
    insert_especialidad("Ortopedia y Traumatología", "Lesiones y enfermedades del sistema músculo-esquelético.")
    insert_especialidad("Psicología Clínica", "Atención psicológica y seguimiento clínico.")
    insert_especialidad("Odontología", "Salud bucal y dental.")
    insert_especialidad("Oftalmología", "Enfermedades oculares.")
    insert_especialidad("Otorrinolaringología", "Enfermedades de oído, nariz y garganta.")
    insert_especialidad("Gastroenterología", "Enfermedades del sistema digestivo.")
    insert_especialidad("Urología", "Enfermedades del sistema urinario.")
    insert_especialidad("Endocrinología", "Trastornos hormonales y metabólicos.")
    insert_especialidad("Psiquiatría", "Atención especializada en salud mental.")
    insert_especialidad("Nutrición", "Evaluación y seguimiento nutricional.")
    insert_especialidad("Medicina Interna", "Diagnóstico y tratamiento de enfermedades internas.")
    insert_especialidad("Cirugía General", "Procedimientos quirúrgicos generales.")

    # Catálogos útiles para citas y pagos.
    insert_estado_cita("Programada", "#38bdf8")
    insert_estado_cita("Confirmada", "#22c55e")
    insert_estado_cita("Completada", "#8b5cf6")
    insert_estado_cita("Cancelada", "#ef4444")
    insert_estado_cita("No asistió", "#f97316")

    insert_motivo("Consulta general", "Consulta médica general.")
    insert_motivo("Seguimiento", "Consulta de seguimiento clínico.")
    insert_motivo("Evaluación inicial", "Primera evaluación del paciente.")
    insert_motivo("Emergencia", "Atención prioritaria.")

    insert_tipo_pago("Efectivo")
    insert_tipo_pago("Tarjeta")
    insert_tipo_pago("Transferencia")
    insert_tipo_pago("Depósito")

    print("Catálogos base verificados/creados correctamente.")


if __name__ == "__main__":
    main()
