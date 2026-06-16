from .common import *  # noqa: F401,F403


def _validar_datos_paciente(body):
    """Devuelve un mensaje de error si los datos del paciente son inválidos, o None."""
    correo = (body.get('correo') or '').strip()
    if correo and not _email_valido(correo):
        return 'El correo electrónico no es válido.'
    fn = body.get('fecha_nacimiento')
    if fn:
        try:
            if date.fromisoformat(str(fn)) > date.today():
                return 'La fecha de nacimiento no puede ser futura.'
        except ValueError:
            return 'La fecha de nacimiento no es válida.'
    return None


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
@ensure_csrf_cookie
def pacientes_page(request):
    return render(request, 'core/pacientes.html')


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def pacientes_json(request):
    pacientes_qs = Pacientes.objects.all()

    # Un Doctor solo ve los pacientes que han tenido cita con él.
    if _es_doctor(request):
        doctor = _doctor_de_sesion(request)
        if not doctor:
            return JsonResponse([], safe=False, json_dumps_params={'ensure_ascii': False})
        ids_pacientes = Citas.objects.filter(
            id_doctor=doctor
        ).values_list('id_paciente_id', flat=True)
        pacientes_qs = pacientes_qs.filter(id_paciente__in=ids_pacientes)

    busqueda = request.GET.get('search', '').strip()
    if busqueda:
        pacientes_qs = pacientes_qs.filter(
            Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(dpi_pasaporte__icontains=busqueda)
            | Q(telefono__icontains=busqueda)
            | Q(correo__icontains=busqueda)
        )

    data = list(
        pacientes_qs.values(
            'id_paciente',
            'nombres',
            'apellidos',
            'fecha_nacimiento',
            'sexo',
            'dpi_pasaporte',
            'direccion',
            'telefono',
            'correo',
            'ocupacion',
            'contacto_emergencia_nombre',
            'contacto_emergencia_telefono',
            'activo'
        )
    )

    paginado = _aplicar_paginacion(request, data)
    if paginado is not None:
        return JsonResponse(paginado, json_dumps_params={'ensure_ascii': False})
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción'])
def crear_paciente_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        error_val = _validar_datos_paciente(body)
        if error_val:
            return JsonResponse({'ok': False, 'error': error_val}, status=400)

        nuevo_paciente = Pacientes.objects.create(
            nombres=body.get('nombres', ''),
            apellidos=body.get('apellidos', ''),
            fecha_nacimiento=body.get('fecha_nacimiento') or None,
            sexo=body.get('sexo', ''),
            dpi_pasaporte=body.get('dpi_pasaporte', ''),
            direccion=body.get('direccion', ''),
            telefono=body.get('telefono', ''),
            correo=body.get('correo', ''),
            ocupacion=body.get('ocupacion', ''),
            contacto_emergencia_nombre=body.get('contacto_emergencia_nombre', ''),
            contacto_emergencia_telefono=body.get('contacto_emergencia_telefono', ''),
            activo=1
        )

        registrar_auditoria(
            request.session.get('usuario_id'), 'pacientes', nuevo_paciente.id_paciente,
            'crear', f"Paciente creado: {nuevo_paciente.nombres} {nuevo_paciente.apellidos}".strip()
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Paciente creado correctamente',
            'id_paciente': nuevo_paciente.id_paciente
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def actualizar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        error_val = _validar_datos_paciente(body)
        if error_val:
            return JsonResponse({'ok': False, 'error': error_val}, status=400)

        paciente = Pacientes.objects.get(id_paciente=id_paciente)

        paciente.nombres = body.get('nombres', '')
        paciente.apellidos = body.get('apellidos', '')
        paciente.fecha_nacimiento = body.get('fecha_nacimiento') or None
        paciente.sexo = body.get('sexo', '')
        paciente.dpi_pasaporte = body.get('dpi_pasaporte', '')
        paciente.direccion = body.get('direccion', '')
        paciente.telefono = body.get('telefono', '')
        paciente.correo = body.get('correo', '')
        paciente.ocupacion = body.get('ocupacion', '')
        paciente.contacto_emergencia_nombre = body.get('contacto_emergencia_nombre', '')
        paciente.contacto_emergencia_telefono = body.get('contacto_emergencia_telefono', '')

        paciente.save()

        registrar_auditoria(
            request.session.get('usuario_id'), 'pacientes', paciente.id_paciente,
            'editar', f"Paciente actualizado: {paciente.nombres} {paciente.apellidos}".strip()
        )

        return JsonResponse({'ok': True, 'mensaje': 'Paciente actualizado'}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def desactivar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        paciente = Pacientes.objects.get(id_paciente=id_paciente)
        paciente.activo = 0
        paciente.save()

        registrar_auditoria(request.session.get('usuario_id'), 'pacientes', paciente.id_paciente, 'desactivar', 'Paciente desactivado')

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def activar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        paciente = Pacientes.objects.get(id_paciente=id_paciente)
        paciente.activo = 1
        paciente.save()

        registrar_auditoria(request.session.get('usuario_id'), 'pacientes', paciente.id_paciente, 'activar', 'Paciente activado')

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def generar_word_paciente(request, id_paciente):
    paciente = get_object_or_404(Pacientes, id_paciente=id_paciente)

    def valor(valor_original):
        if valor_original is None or valor_original == "":
            return "No registrado"
        return str(valor_original)

    def fecha(valor_fecha):
        if not valor_fecha:
            return "No registrado"
        try:
            return valor_fecha.strftime("%Y-%m-%d")
        except Exception:
            return str(valor_fecha)

    def fecha_hora(valor_fecha):
        if not valor_fecha:
            return "No registrado"
        try:
            return valor_fecha.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(valor_fecha)

    def hora(valor_hora):
        if not valor_hora:
            return "No registrado"
        try:
            return valor_hora.strftime("%H:%M")
        except Exception:
            return str(valor_hora)

    def aplicar_fuente(documento):
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

    def agregar_tabla_dos_columnas(documento, datos):
        tabla = documento.add_table(rows=0, cols=2)
        tabla.style = "Table Grid"

        for etiqueta, dato in datos:
            fila = tabla.add_row().cells
            fila[0].text = str(etiqueta)
            fila[1].text = valor(dato)

        return tabla

    def agregar_tabla_registros(documento, encabezados, registros):
        tabla = documento.add_table(rows=1, cols=len(encabezados))
        tabla.style = "Table Grid"

        for i, encabezado in enumerate(encabezados):
            tabla.rows[0].cells[i].text = str(encabezado)

        for registro in registros:
            fila = tabla.add_row().cells
            for i, dato in enumerate(registro):
                fila[i].text = valor(dato)

        return tabla

    documento = Document()

    titulo = documento.add_heading("Reporte Clínico del Paciente", level=1)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER

    documento.add_paragraph("Clínica Médica DS")
    documento.add_paragraph("Documento generado desde el sistema clínico.")
    documento.add_paragraph("")

    # =========================
    # DATOS DEL PACIENTE
    # =========================
    documento.add_heading("Datos del paciente", level=2)

    datos_paciente = [
        ("ID", paciente.id_paciente),
        ("Nombres", paciente.nombres),
        ("Apellidos", paciente.apellidos),
        ("Fecha de nacimiento", fecha(paciente.fecha_nacimiento)),
        ("Sexo", paciente.sexo),
        ("DPI / Pasaporte", paciente.dpi_pasaporte),
        ("Dirección", paciente.direccion),
        ("Teléfono", paciente.telefono),
        ("Correo", paciente.correo),
        ("Ocupación", paciente.ocupacion),
        ("Contacto de emergencia", paciente.contacto_emergencia_nombre),
        ("Teléfono de emergencia", paciente.contacto_emergencia_telefono),
        ("Activo", "Sí" if paciente.activo else "No"),
    ]

    agregar_tabla_dos_columnas(documento, datos_paciente)
    documento.add_paragraph("")

    # =========================
    # CITAS
    # =========================
    documento.add_heading("Historial de citas", level=2)

    citas = Citas.objects.select_related(
        "id_doctor__id_usuario",
        "id_estado_cita",
        "id_motivo_consulta"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_cita", "-hora_inicio", "-id_cita")

    if citas.exists():
        registros_citas = []

        for cita in citas:
            doctor = "No asignado"
            if cita.id_doctor and cita.id_doctor.id_usuario:
                doctor = f"{cita.id_doctor.id_usuario.nombres} {cita.id_doctor.id_usuario.apellidos}"

            estado = cita.id_estado_cita.nombre_estado if cita.id_estado_cita else "Sin estado"
            motivo = cita.id_motivo_consulta.nombre_motivo if cita.id_motivo_consulta else "Sin motivo"

            registros_citas.append([
                cita.id_cita,
                fecha(cita.fecha_cita),
                hora(cita.hora_inicio),
                hora(cita.hora_fin),
                doctor,
                estado,
                motivo,
                cita.modalidad,
                cita.razon_consulta_detalle,
                cita.observaciones,
            ])

        agregar_tabla_registros(
            documento,
            [
                "ID cita",
                "Fecha",
                "Inicio",
                "Fin",
                "Doctor",
                "Estado",
                "Motivo",
                "Modalidad",
                "Detalle",
                "Observaciones",
            ],
            registros_citas
        )
    else:
        documento.add_paragraph("No hay citas registradas para este paciente.")

    documento.add_paragraph("")

    # =========================
    # NOTAS CLÍNICAS
    # =========================
    documento.add_heading("Notas clínicas", level=2)

    notas = NotasClinicas.objects.select_related(
        "id_cita",
        "id_doctor__id_usuario"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_nota", "-id_nota_clinica")

    if notas.exists():
        for nota in notas:
            doctor = "No asignado"
            if nota.id_doctor and nota.id_doctor.id_usuario:
                doctor = f"{nota.id_doctor.id_usuario.nombres} {nota.id_doctor.id_usuario.apellidos}"

            documento.add_paragraph(f"Nota #{nota.id_nota_clinica}", style="List Bullet")
            agregar_tabla_dos_columnas(
                documento,
                [
                    ("Fecha", fecha_hora(nota.fecha_nota)),
                    ("Cita relacionada", nota.id_cita.id_cita if nota.id_cita else "No registrada"),
                    ("Doctor", doctor),
                    ("Título", nota.titulo),
                    ("Contenido", nota.contenido),
                    ("Recomendaciones", nota.recomendaciones),
                ]
            )
            documento.add_paragraph("")
    else:
        documento.add_paragraph("No hay notas clínicas registradas para este paciente.")

    documento.add_paragraph("")

    # =========================
    # PAGOS
    # =========================
    documento.add_heading("Pagos registrados", level=2)

    pagos = Pagos.objects.select_related(
        "id_cita",
        "id_tipo_pago"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_pago", "-id_pago")

    if pagos.exists():
        registros_pagos = []

        for pago in pagos:
            tipo_pago = pago.id_tipo_pago.nombre_tipo_pago if pago.id_tipo_pago else "Sin tipo"

            registros_pagos.append([
                pago.id_pago,
                pago.id_cita.id_cita if pago.id_cita else "No registrada",
                tipo_pago,
                f"Q {pago.monto}",
                fecha_hora(pago.fecha_pago),
                pago.referencia_pago,
                pago.observaciones,
            ])

        agregar_tabla_registros(
            documento,
            [
                "ID pago",
                "ID cita",
                "Tipo de pago",
                "Monto",
                "Fecha de pago",
                "Referencia",
                "Observaciones",
            ],
            registros_pagos
        )
    else:
        documento.add_paragraph("No hay pagos registrados para este paciente.")

    documento.add_paragraph("")

    # =========================
    # FACTURA / COMPROBANTE
    # =========================
    documento.add_heading("Factura / Comprobante de Pago", level=2)

    cita_factura = citas.filter(
        id_estado_cita__nombre_estado='Completada'
    ).order_by('-fecha_cita', '-hora_inicio').first() or citas.order_by('-fecha_cita', '-hora_inicio').first()

    pago_factura = pagos.first()

    tabla_factura = documento.add_table(rows=0, cols=2)
    tabla_factura.style = "Table Grid"

    def fila_factura(tabla, etiqueta, dato):
        fila = tabla.add_row().cells
        fila[0].text = str(etiqueta)
        fila[1].text = str(dato) if dato not in (None, '') else ''

    fila_factura(tabla_factura, "Paciente", f"{paciente.nombres or ''} {paciente.apellidos or ''}".strip())
    fila_factura(tabla_factura, "DPI / Pasaporte", paciente.dpi_pasaporte or '')
    fila_factura(tabla_factura, "Teléfono", paciente.telefono or '')
    fila_factura(tabla_factura, "Correo", paciente.correo or '')

    if cita_factura:
        doctor_fact = ''
        if cita_factura.id_doctor and cita_factura.id_doctor.id_usuario:
            u = cita_factura.id_doctor.id_usuario
            doctor_fact = f"{u.nombres or ''} {u.apellidos or ''}".strip()
        especialidad_fact = ''
        if cita_factura.id_doctor and cita_factura.id_doctor.id_especialidad:
            especialidad_fact = cita_factura.id_doctor.id_especialidad.nombre_especialidad or ''

        fila_factura(tabla_factura, "Fecha de consulta", fecha(cita_factura.fecha_cita))
        fila_factura(tabla_factura, "Horario", f"{hora(cita_factura.hora_inicio)} - {hora(cita_factura.hora_fin)}")
        fila_factura(tabla_factura, "Doctor", doctor_fact)
        fila_factura(tabla_factura, "Especialidad", especialidad_fact)
        fila_factura(tabla_factura, "Modalidad", cita_factura.modalidad or 'Presencial')
        fila_factura(tabla_factura, "Motivo", cita_factura.id_motivo_consulta.nombre_motivo if cita_factura.id_motivo_consulta else '')

    fila_factura(tabla_factura, "Forma de pago", pago_factura.id_tipo_pago.nombre_tipo_pago if pago_factura and pago_factura.id_tipo_pago else '')
    fila_factura(tabla_factura, "Monto (Q)", f"{pago_factura.monto}" if pago_factura and pago_factura.monto is not None else '')
    fila_factura(tabla_factura, "Referencia", pago_factura.referencia_pago if pago_factura else '')
    fila_factura(tabla_factura, "Observaciones de pago", pago_factura.observaciones if pago_factura else '')
    fila_factura(tabla_factura, "Firma del paciente", '')
    fila_factura(tabla_factura, "Sello y firma del médico", '')

    documento.add_paragraph("")

    aplicar_fuente(documento)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    nombre_archivo = f"reporte_paciente_{paciente.id_paciente}.docx"
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'

    documento.save(response)
    return response


@rol_requerido(['Administrador', 'Recepción'])
def generar_factura_paciente(request, id_paciente):
    paciente = get_object_or_404(Pacientes, id_paciente=id_paciente)

    config = ConfiguracionClinica.objects.first()
    nombre_clinica = (config.nombre_clinica if config else None) or 'Clínica DS'

    ultima_cita = (
        Citas.objects.filter(id_paciente=paciente)
        .select_related('id_doctor__id_usuario', 'id_doctor__id_especialidad', 'id_estado_cita', 'id_motivo_consulta')
        .order_by('-fecha_cita', '-id_cita')
        .first()
    )
    pago_factura = (
        Pagos.objects.filter(id_cita=ultima_cita).select_related('id_tipo_pago').first()
        if ultima_cita else None
    )

    def _v(v):
        return str(v).strip() if v not in (None, '') else ''

    def _fecha(v):
        try:
            return v.strftime('%d/%m/%Y')
        except Exception:
            return _v(v)

    def _hora(v):
        try:
            return v.strftime('%H:%M')
        except Exception:
            return _v(v)

    def _sombra(cell, color):
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), color)
        tc_pr.append(shd)

    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Cm(2)
        sec.bottom_margin = Cm(2.5)
        sec.left_margin = Cm(2.5)
        sec.right_margin = Cm(2.5)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(nombre_clinica.upper())
    r.bold = True
    r.font.size = Pt(18)
    r.font.name = 'Arial'
    r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run('COMPROBANTE DE CONSULTA MÉDICA')
    r2.bold = True
    r2.font.size = Pt(11)
    r2.font.name = 'Arial'
    r2.font.color.rgb = RGBColor(0x2C, 0x7B, 0xB0)

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r3 = p3.add_run(f'Fecha de emisión: {date.today().strftime("%d/%m/%Y")}')
    r3.font.size = Pt(9)
    r3.font.name = 'Arial'

    doc.add_paragraph('')

    C_HDR = '1E3A5F'
    C_LBL = 'D6EAF8'
    C_VAL = 'FFFFFF'

    tabla = doc.add_table(rows=0, cols=2)
    tabla.style = 'Table Grid'

    def _hdr(texto):
        row = tabla.add_row()
        row.cells[0].merge(row.cells[1])
        row.cells[0].text = texto
        _sombra(row.cells[0], C_HDR)
        for para in row.cells[0].paragraphs:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                run.bold = True
                run.font.name = 'Arial'
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    def _dato(lbl, val_txt):
        row = tabla.add_row()
        row.cells[0].text = lbl
        row.cells[1].text = val_txt
        _sombra(row.cells[0], C_LBL)
        _sombra(row.cells[1], C_VAL)
        for para in row.cells[0].paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.name = 'Arial'
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)
        for para in row.cells[1].paragraphs:
            for run in para.runs:
                run.font.name = 'Arial'
                run.font.size = Pt(9)

    _hdr('DATOS DEL PACIENTE')
    _dato('Paciente', f"{_v(paciente.nombres)} {_v(paciente.apellidos)}".strip())
    _dato('DPI / Pasaporte', _v(paciente.dpi_pasaporte))
    _dato('Teléfono', _v(paciente.telefono))
    _dato('Correo electrónico', _v(paciente.correo))

    _hdr('DATOS DE LA CONSULTA')
    if ultima_cita:
        dr_nombre = ''
        if ultima_cita.id_doctor and ultima_cita.id_doctor.id_usuario:
            u = ultima_cita.id_doctor.id_usuario
            dr_nombre = f"{_v(u.nombres)} {_v(u.apellidos)}".strip()
        esp_nombre = ''
        if ultima_cita.id_doctor and ultima_cita.id_doctor.id_especialidad:
            esp_nombre = _v(ultima_cita.id_doctor.id_especialidad.nombre_especialidad)
        h_ini = _hora(ultima_cita.hora_inicio)
        h_fin = _hora(ultima_cita.hora_fin)
        horario = f'{h_ini} - {h_fin}' if h_ini or h_fin else ''
        _dato('Fecha de consulta', _fecha(ultima_cita.fecha_cita))
        _dato('Horario', horario)
        _dato('Doctor', dr_nombre)
        _dato('Especialidad', esp_nombre)
        _dato('Modalidad', _v(ultima_cita.modalidad) or 'Presencial')
        motivo_txt = _v(ultima_cita.id_motivo_consulta.nombre_motivo) if ultima_cita.id_motivo_consulta else ''
        _dato('Motivo de consulta', motivo_txt)
        estado_txt = _v(ultima_cita.id_estado_cita.nombre_estado) if ultima_cita.id_estado_cita else ''
        _dato('Estado', estado_txt)
    else:
        _dato('Sin citas registradas', '')

    _hdr('INFORMACIÓN DE PAGO')
    _dato('Forma de pago', '')
    _dato('Monto (Q)', f'{pago_factura.monto}' if pago_factura and pago_factura.monto is not None else '')
    _dato('Referencia', _v(pago_factura.referencia_pago) if pago_factura else '')
    _dato('Observaciones', _v(pago_factura.observaciones) if pago_factura else '')

    _hdr('FIRMAS')
    _dato('Firma del paciente', '')
    _dato('Sello y firma del médico', '')

    doc.add_paragraph('')

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    resp['Content-Disposition'] = f'attachment; filename="factura_{paciente.id_paciente}.docx"'
    doc.save(resp)
    return resp
