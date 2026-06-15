from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def _datos_reporte_general():
    def fetchone_val(sql, params=None, default=0):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                row = cursor.fetchone()
            if not row:
                return default
            return row[0] if row[0] is not None else default
        except Exception as e:
            print("ERROR REPORTE fetchone:", e, sql)
            return default

    def fetchall(sql, params=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                return cursor.fetchall()
        except Exception as e:
            print("ERROR REPORTE fetchall:", e, sql)
            return []

    hoy = timezone.localdate()
    ahora = timezone.now()

    total_pacientes = int(fetchone_val("SELECT COUNT(*) FROM pacientes WHERE activo = 1"))
    total_pacientes_general = int(fetchone_val("SELECT COUNT(*) FROM pacientes"))
    total_usuarios = int(fetchone_val("SELECT COUNT(*) FROM usuarios"))
    usuarios_activos = int(fetchone_val("SELECT COUNT(*) FROM usuarios WHERE activo = 1"))
    total_doctores = int(fetchone_val("SELECT COUNT(*) FROM doctores"))
    doctores_activos = int(fetchone_val("SELECT COUNT(*) FROM doctores WHERE activo = 1"))
    total_citas = int(fetchone_val("SELECT COUNT(*) FROM citas"))
    total_pagos = int(fetchone_val("SELECT COUNT(*) FROM pagos"))

    citas_hoy = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita = CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    citas_proximas_total = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita >= CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    ingresos_totales = float(fetchone_val("SELECT COALESCE(SUM(monto),0) FROM pagos", default=0) or 0)
    pagos_del_mes = float(fetchone_val("""
        SELECT COALESCE(SUM(monto),0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND MONTH(fecha_pago) = MONTH(CURDATE())
          AND YEAR(fecha_pago) = YEAR(CURDATE())
    """, default=0) or 0)
    ingresos_semanales = float(fetchone_val("""
        SELECT COALESCE(SUM(monto),0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND fecha_pago >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, default=0) or 0)

    promedio_pago = round((ingresos_totales / total_pagos), 2) if total_pagos else 0
    citas_futuras_pendientes_pago = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN pagos p ON c.id_cita = p.id_cita
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita >= CURDATE()
          AND p.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))
    ingresos_potenciales = round(promedio_pago * citas_futuras_pendientes_pago, 2)

    canceladas = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        INNER JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE LOWER(e.nombre_estado) IN ('cancelada', 'cancelado')
    """))
    tasa_cancelaciones = round((canceladas / total_citas) * 100, 2) if total_citas else 0

    citas_por_estado = []
    for estado, total in fetchall("""
        SELECT COALESCE(e.nombre_estado, 'Sin estado') AS estado, COUNT(c.id_cita) AS total
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        GROUP BY estado
        ORDER BY total DESC
    """):
        citas_por_estado.append({'estado': estado, 'total': int(total or 0)})

    pacientes_frecuentes = []
    for id_paciente, nombres, apellidos, total in fetchall("""
        SELECT p.id_paciente, p.nombres, p.apellidos, COUNT(c.id_cita) AS total
        FROM citas c
        INNER JOIN pacientes p ON c.id_paciente = p.id_paciente
        GROUP BY p.id_paciente, p.nombres, p.apellidos
        ORDER BY total DESC
        LIMIT 10
    """):
        pacientes_frecuentes.append({
            'id_paciente': id_paciente,
            'paciente': f"{nombres or ''} {apellidos or ''}".strip(),
            'total_citas': int(total or 0)
        })

    cumpleanios_mes = []
    for id_paciente, nombres, apellidos, fecha_nacimiento in fetchall("""
        SELECT id_paciente, nombres, apellidos, fecha_nacimiento
        FROM pacientes
        WHERE activo = 1
          AND fecha_nacimiento IS NOT NULL
          AND MONTH(fecha_nacimiento) = MONTH(CURDATE())
        ORDER BY DAY(fecha_nacimiento), nombres
    """):
        cumpleanios_mes.append({
            'id_paciente': id_paciente,
            'paciente': f"{nombres or ''} {apellidos or ''}".strip(),
            'fecha_nacimiento': str(fecha_nacimiento) if fecha_nacimiento else ''
        })

    ingresos_por_tipo = []
    for tipo, cantidad, total in fetchall("""
        SELECT COALESCE(t.nombre_tipo_pago, 'Sin tipo') AS tipo, COUNT(p.id_pago) AS cantidad, COALESCE(SUM(p.monto),0) AS total
        FROM pagos p
        LEFT JOIN tipos_pago t ON p.id_tipo_pago = t.id_tipo_pago
        GROUP BY tipo
        ORDER BY total DESC
    """):
        ingresos_por_tipo.append({
            'tipo_pago': tipo,
            'cantidad': int(cantidad or 0),
            'total': float(total or 0)
        })

    citas_proximas = []
    for row in fetchall("""
        SELECT
            c.id_cita,
            p.nombres,
            p.apellidos,
            ud.nombres,
            ud.apellidos,
            c.fecha_cita,
            c.hora_inicio,
            c.hora_fin,
            COALESCE(e.nombre_estado, 'Sin estado') AS estado,
            COALESCE(c.modalidad, '') AS modalidad,
            COALESCE(m.nombre_motivo, '') AS motivo,
            COALESCE(c.razon_consulta_detalle, '') AS detalle
        FROM citas c
        LEFT JOIN pacientes p ON c.id_paciente = p.id_paciente
        LEFT JOIN doctores d ON c.id_doctor = d.id_doctor
        LEFT JOIN usuarios ud ON d.id_usuario = ud.id_usuario
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        LEFT JOIN motivos_consulta m ON c.id_motivo_consulta = m.id_motivo_consulta
        WHERE c.fecha_cita >= CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita ASC, c.hora_inicio ASC
        LIMIT 30
    """):
        (id_cita, pn, pa, dn, da, fecha_cita, hora_inicio, hora_fin, estado, modalidad, motivo, detalle) = row
        citas_proximas.append({
            'id_cita': id_cita,
            'paciente': f"{pn or ''} {pa or ''}".strip(),
            'doctor': f"{dn or ''} {da or ''}".strip(),
            'fecha_cita': str(fecha_cita) if fecha_cita else '',
            'hora_inicio': str(hora_inicio)[:5] if hora_inicio else '',
            'hora_fin': str(hora_fin)[:5] if hora_fin else '',
            'estado': estado,
            'modalidad': modalidad,
            'motivo': motivo,
            'detalle': detalle
        })

    sesiones_pendientes = []
    for row in fetchall("""
        SELECT
            c.id_cita,
            p.nombres,
            p.apellidos,
            ud.nombres,
            ud.apellidos,
            c.fecha_cita,
            c.hora_inicio,
            COALESCE(e.nombre_estado, 'Sin estado') AS estado
        FROM citas c
        LEFT JOIN pagos pg ON c.id_cita = pg.id_cita
        LEFT JOIN pacientes p ON c.id_paciente = p.id_paciente
        LEFT JOIN doctores d ON c.id_doctor = d.id_doctor
        LEFT JOIN usuarios ud ON d.id_usuario = ud.id_usuario
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE pg.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita DESC, c.hora_inicio DESC
        LIMIT 30
    """):
        (id_cita, pn, pa, dn, da, fecha_cita, hora_inicio, estado) = row
        sesiones_pendientes.append({
            'id_cita': id_cita,
            'paciente': f"{pn or ''} {pa or ''}".strip(),
            'doctor': f"{dn or ''} {da or ''}".strip(),
            'fecha_cita': str(fecha_cita) if fecha_cita else '',
            'hora_inicio': str(hora_inicio)[:5] if hora_inicio else '',
            'estado': estado
        })

    usuarios_resumen = []
    for row in fetchall("""
        SELECT u.id_usuario, u.username, u.nombres, u.apellidos, COALESCE(r.nombre_rol, '') AS rol, u.correo, u.activo
        FROM usuarios u
        LEFT JOIN roles r ON u.id_rol = r.id_rol
        ORDER BY u.id_usuario DESC
        LIMIT 50
    """):
        id_usuario, username, nombres, apellidos, rol, correo, activo = row
        usuarios_resumen.append({
            'id_usuario': id_usuario,
            'usuario': username or '',
            'nombre': f"{nombres or ''} {apellidos or ''}".strip(),
            'rol': rol,
            'correo': correo or '',
            'activo': int(activo or 0)
        })

    doctores_resumen = []
    for row in fetchall("""
        SELECT d.id_doctor, u.nombres, u.apellidos, COALESCE(e.nombre_especialidad, '') AS especialidad,
               u.correo, u.telefono, d.numero_colegiado, d.activo
        FROM doctores d
        LEFT JOIN usuarios u ON d.id_usuario = u.id_usuario
        LEFT JOIN especialidades e ON d.id_especialidad = e.id_especialidad
        ORDER BY d.id_doctor DESC
        LIMIT 50
    """):
        id_doctor, nombres, apellidos, especialidad, correo, telefono, colegiado, activo = row
        doctores_resumen.append({
            'id_doctor': id_doctor,
            'doctor': f"{nombres or ''} {apellidos or ''}".strip(),
            'especialidad': especialidad,
            'correo': correo or '',
            'telefono': telefono or '',
            'colegiado': colegiado or '',
            'activo': int(activo or 0)
        })

    return {
        'fecha_generacion': ahora.strftime('%Y-%m-%d %H:%M:%S'),
        'total_pacientes': total_pacientes,
        'total_pacientes_general': total_pacientes_general,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'total_doctores': total_doctores,
        'doctores_activos': doctores_activos,
        'total_citas': total_citas,
        'citas_hoy': citas_hoy,
        'citas_proximas_total': citas_proximas_total,
        'total_pagos': total_pagos,
        'ingresos_totales': ingresos_totales,
        'pagos_del_mes': pagos_del_mes,
        'ingresos_semanales': ingresos_semanales,
        'ingresos_potenciales': ingresos_potenciales,
        'citas_futuras_pendientes_pago': citas_futuras_pendientes_pago,
        'promedio_pago': promedio_pago,
        'tasa_cancelaciones': tasa_cancelaciones,
        'citas_por_estado': citas_por_estado,
        'pacientes_frecuentes': pacientes_frecuentes,
        'cumpleanios_mes': cumpleanios_mes,
        'ingresos_por_tipo': ingresos_por_tipo,
        'citas_proximas': citas_proximas,
        'sesiones_pendientes': sesiones_pendientes,
        'usuarios_resumen': usuarios_resumen,
        'doctores_resumen': doctores_resumen,
    }


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def generar_word_reporte_general(request):
    data = _datos_reporte_general()

    def valor(v):
        if v is None or v == '':
            return 'No registrado'
        return str(v)

    def agregar_tabla(documento, encabezados, filas):
        tabla = documento.add_table(rows=1, cols=len(encabezados))
        tabla.style = "Table Grid"
        for i, encabezado in enumerate(encabezados):
            tabla.rows[0].cells[i].text = str(encabezado)
        for fila_data in filas:
            fila = tabla.add_row().cells
            for i, dato in enumerate(fila_data):
                fila[i].text = valor(dato)
        return tabla

    documento = Document()
    titulo = documento.add_heading("Reporte General del Sistema Clínico", level=1)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    documento.add_paragraph("Clínica DS")
    documento.add_paragraph(f"Fecha de generación: {data.get('fecha_generacion')}")
    documento.add_paragraph("")

    documento.add_heading("Resumen general", level=2)
    agregar_tabla(documento, ["Indicador", "Valor"], [
        ["Pacientes activos", data.get('total_pacientes')],
        ["Pacientes registrados", data.get('total_pacientes_general')],
        ["Usuarios totales", data.get('total_usuarios')],
        ["Usuarios activos", data.get('usuarios_activos')],
        ["Doctores totales", data.get('total_doctores')],
        ["Doctores activos", data.get('doctores_activos')],
        ["Total citas", data.get('total_citas')],
        ["Citas de hoy", data.get('citas_hoy')],
        ["Citas próximas", data.get('citas_proximas_total')],
        ["Total pagos", data.get('total_pagos')],
        ["Ingresos totales", f"Q{float(data.get('ingresos_totales', 0)):.2f}"],
        ["Ingresos del mes", f"Q{float(data.get('pagos_del_mes', 0)):.2f}"],
        ["Ingresos semanales", f"Q{float(data.get('ingresos_semanales', 0)):.2f}"],
        ["Ingresos potenciales", f"Q{float(data.get('ingresos_potenciales', 0)):.2f}"],
        ["Tasa de cancelaciones", f"{data.get('tasa_cancelaciones')}%"],
    ])

    secciones = [
        ("Citas por estado", ["Estado", "Total"], [[x.get('estado'), x.get('total')] for x in data.get('citas_por_estado', [])]),
        ("Ingresos por tipo de pago", ["Tipo", "Cantidad", "Total"], [[x.get('tipo_pago'), x.get('cantidad'), f"Q{float(x.get('total', 0)):.2f}"] for x in data.get('ingresos_por_tipo', [])]),
        ("Citas próximas", ["ID", "Paciente", "Doctor", "Fecha", "Inicio", "Fin", "Estado", "Modalidad", "Motivo"], [[x.get('id_cita'), x.get('paciente'), x.get('doctor'), x.get('fecha_cita'), x.get('hora_inicio'), x.get('hora_fin'), x.get('estado'), x.get('modalidad'), x.get('motivo')] for x in data.get('citas_proximas', [])]),
        ("Pacientes frecuentes", ["Paciente", "Total citas"], [[x.get('paciente'), x.get('total_citas')] for x in data.get('pacientes_frecuentes', [])]),
        ("Doctores", ["ID", "Doctor", "Especialidad", "Correo", "Teléfono", "Colegiado", "Activo"], [[x.get('id_doctor'), x.get('doctor'), x.get('especialidad'), x.get('correo'), x.get('telefono'), x.get('colegiado'), "Sí" if x.get('activo') else "No"] for x in data.get('doctores_resumen', [])]),
        ("Usuarios", ["ID", "Usuario", "Nombre", "Rol", "Correo", "Activo"], [[x.get('id_usuario'), x.get('usuario'), x.get('nombre'), x.get('rol'), x.get('correo'), "Sí" if x.get('activo') else "No"] for x in data.get('usuarios_resumen', [])]),
        ("Sesiones pendientes de pago", ["Cita", "Paciente", "Doctor", "Fecha", "Hora", "Estado"], [[x.get('id_cita'), x.get('paciente'), x.get('doctor'), x.get('fecha_cita'), x.get('hora_inicio'), x.get('estado')] for x in data.get('sesiones_pendientes', [])]),
    ]

    for titulo_seccion, encabezados, filas in secciones:
        documento.add_paragraph("")
        documento.add_heading(titulo_seccion, level=2)
        agregar_tabla(documento, encabezados, filas or [["Sin datos"] + [""] * (len(encabezados) - 1)])

    for parrafo in documento.paragraphs:
        for run in parrafo.runs:
            run.font.name = "Arial"
            run.font.size = Pt(11)

    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    for run in parrafo.runs:
                        run.font.name = "Arial"
                        run.font.size = Pt(9)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    response["Content-Disposition"] = 'attachment; filename="reporte_general_clinica.docx"'
    documento.save(response)
    return response
