from .common import *  # noqa: F401,F403


def _datos_reporte_general():
    """Reúne los indicadores del reporte general usando el ORM (portable en
    PostgreSQL y otros motores; no usa funciones específicas de MySQL)."""
    from django.db.models.functions import ExtractDay

    def excluir_canceladas(qs):
        return qs.exclude(
            id_estado_cita__nombre_estado__iexact='cancelada'
        ).exclude(
            id_estado_cita__nombre_estado__iexact='cancelado'
        )

    def fdate(v):
        return str(v) if v else ''

    def fhora(v):
        return str(v)[:5] if v else ''

    def nombre_pac(c):
        if not c.id_paciente:
            return ''
        return f"{c.id_paciente.nombres or ''} {c.id_paciente.apellidos or ''}".strip()

    def nombre_doc(c):
        if c.id_doctor and c.id_doctor.id_usuario:
            u = c.id_doctor.id_usuario
            return f"{u.nombres or ''} {u.apellidos or ''}".strip()
        return ''

    hoy = date.today()
    ahora = timezone.now()

    # Los pagos anulados no cuentan como ingreso ni como "cita pagada".
    pagos_validos = Pagos.objects.exclude(estado='anulado')

    total_pacientes = Pacientes.objects.filter(activo=1).count()
    total_pacientes_general = Pacientes.objects.count()
    total_usuarios = Usuarios.objects.count()
    usuarios_activos = Usuarios.objects.filter(activo=1).count()
    total_doctores = Doctores.objects.count()
    doctores_activos = Doctores.objects.filter(activo=1).count()
    total_citas = Citas.objects.count()
    total_pagos = pagos_validos.count()

    citas_hoy = excluir_canceladas(Citas.objects.filter(fecha_cita=hoy)).count()
    citas_proximas_total = excluir_canceladas(Citas.objects.filter(fecha_cita__gte=hoy)).count()

    ingresos_totales = float(pagos_validos.aggregate(t=Sum('monto'))['t'] or 0)
    pagos_del_mes = float(
        pagos_validos.filter(
            fecha_pago__isnull=False, fecha_pago__year=hoy.year, fecha_pago__month=hoy.month
        ).aggregate(t=Sum('monto'))['t'] or 0
    )
    ingresos_semanales = float(
        pagos_validos.filter(
            fecha_pago__isnull=False, fecha_pago__gte=ahora - timedelta(days=7)
        ).aggregate(t=Sum('monto'))['t'] or 0
    )

    promedio_pago = round(ingresos_totales / total_pagos, 2) if total_pagos else 0

    citas_con_pago_ids = list(
        pagos_validos.exclude(id_cita__isnull=True).values_list('id_cita_id', flat=True)
    )
    citas_futuras_pendientes_pago = excluir_canceladas(
        Citas.objects.filter(fecha_cita__gte=hoy)
    ).exclude(id_cita__in=citas_con_pago_ids).count()
    ingresos_potenciales = round(promedio_pago * citas_futuras_pendientes_pago, 2)

    canceladas = Citas.objects.filter(
        id_estado_cita__nombre_estado__iexact='cancelada'
    ).count() + Citas.objects.filter(
        id_estado_cita__nombre_estado__iexact='cancelado'
    ).count()
    tasa_cancelaciones = round((canceladas / total_citas) * 100, 2) if total_citas else 0

    citas_por_estado = [
        {'estado': r['id_estado_cita__nombre_estado'] or 'Sin estado', 'total': int(r['total'] or 0)}
        for r in Citas.objects.values('id_estado_cita__nombre_estado')
        .annotate(total=Count('id_cita')).order_by('-total')
    ]

    pacientes_frecuentes = [
        {
            'id_paciente': r['id_paciente'],
            'paciente': f"{r['id_paciente__nombres'] or ''} {r['id_paciente__apellidos'] or ''}".strip(),
            'total_citas': int(r['total'] or 0),
        }
        for r in Citas.objects.filter(id_paciente__isnull=False)
        .values('id_paciente', 'id_paciente__nombres', 'id_paciente__apellidos')
        .annotate(total=Count('id_cita')).order_by('-total')[:10]
    ]

    cumpleanios_mes = [
        {
            'id_paciente': p.id_paciente,
            'paciente': f"{p.nombres or ''} {p.apellidos or ''}".strip(),
            'fecha_nacimiento': str(p.fecha_nacimiento) if p.fecha_nacimiento else '',
        }
        for p in Pacientes.objects.filter(
            activo=1, fecha_nacimiento__isnull=False, fecha_nacimiento__month=hoy.month
        ).annotate(dia=ExtractDay('fecha_nacimiento')).order_by('dia', 'nombres')
    ]

    ingresos_por_tipo = [
        {
            'tipo_pago': r['id_tipo_pago__nombre_tipo_pago'] or 'Sin tipo',
            'cantidad': int(r['cantidad'] or 0),
            'total': float(r['total'] or 0),
        }
        for r in pagos_validos.values('id_tipo_pago__nombre_tipo_pago')
        .annotate(cantidad=Count('id_pago'), total=Sum('monto')).order_by('-total')
    ]

    citas_proximas = []
    for c in excluir_canceladas(
        Citas.objects.filter(fecha_cita__gte=hoy)
    ).select_related(
        'id_paciente', 'id_doctor__id_usuario', 'id_estado_cita', 'id_motivo_consulta'
    ).order_by('fecha_cita', 'hora_inicio')[:30]:
        citas_proximas.append({
            'id_cita': c.id_cita,
            'paciente': nombre_pac(c),
            'doctor': nombre_doc(c),
            'fecha_cita': fdate(c.fecha_cita),
            'hora_inicio': fhora(c.hora_inicio),
            'hora_fin': fhora(c.hora_fin),
            'estado': c.id_estado_cita.nombre_estado if c.id_estado_cita else 'Sin estado',
            'modalidad': c.modalidad or '',
            'motivo': c.id_motivo_consulta.nombre_motivo if c.id_motivo_consulta else '',
            'detalle': c.razon_consulta_detalle or '',
        })

    sesiones_pendientes = []
    for c in excluir_canceladas(Citas.objects.all()).exclude(
        id_cita__in=citas_con_pago_ids
    ).select_related(
        'id_paciente', 'id_doctor__id_usuario', 'id_estado_cita'
    ).order_by('-fecha_cita', '-hora_inicio')[:30]:
        sesiones_pendientes.append({
            'id_cita': c.id_cita,
            'paciente': nombre_pac(c),
            'doctor': nombre_doc(c),
            'fecha_cita': fdate(c.fecha_cita),
            'hora_inicio': fhora(c.hora_inicio),
            'estado': c.id_estado_cita.nombre_estado if c.id_estado_cita else 'Sin estado',
        })

    usuarios_resumen = []
    for u in Usuarios.objects.select_related('id_rol').order_by('-id_usuario')[:50]:
        usuarios_resumen.append({
            'id_usuario': u.id_usuario,
            'usuario': u.username or '',
            'nombre': f"{u.nombres or ''} {u.apellidos or ''}".strip(),
            'rol': u.id_rol.nombre_rol if u.id_rol else '',
            'correo': u.correo or '',
            'activo': int(u.activo or 0),
        })

    doctores_resumen = []
    for d in Doctores.objects.select_related('id_usuario', 'id_especialidad').order_by('-id_doctor')[:50]:
        u = d.id_usuario
        doctores_resumen.append({
            'id_doctor': d.id_doctor,
            'doctor': f"{(u.nombres if u else '') or ''} {(u.apellidos if u else '') or ''}".strip(),
            'especialidad': d.id_especialidad.nombre_especialidad if d.id_especialidad else '',
            'correo': (u.correo if u else '') or '',
            'telefono': (u.telefono if u else '') or '',
            'colegiado': d.numero_colegiado or '',
            'activo': int(d.activo or 0),
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


@rol_requerido(['Administrador'])
def reportes_page(request):
    return render(request, 'core/reportes.html')


@rol_requerido(['Administrador'])
def reportes_json(request):
    try:
        return JsonResponse(_datos_reporte_general(), json_dumps_params={'ensure_ascii': False})
    except Exception:
        logger.exception('Error generando el reporte general')
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)


@rol_requerido(['Administrador'])
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
