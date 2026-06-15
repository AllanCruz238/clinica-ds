from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador', 'Recepción'])
@ensure_csrf_cookie
def pagos_page(request):
    return render(request, 'core/pagos.html')


@rol_requerido(['Administrador', 'Recepción'])
def pagos_json(request):
    pagos = Pagos.objects.select_related(
        'id_paciente',
        'id_cita',
        'id_tipo_pago'
    ).order_by('-id_pago')

    busqueda = request.GET.get('search', '').strip()
    if busqueda:
        pagos = pagos.filter(
            Q(id_paciente__nombres__icontains=busqueda)
            | Q(id_paciente__apellidos__icontains=busqueda)
            | Q(referencia_pago__icontains=busqueda)
        )

    data = []

    for p in pagos:
        data.append({
            'id_pago': p.id_pago,
            'paciente': f"{p.id_paciente.nombres} {p.id_paciente.apellidos}" if p.id_paciente else '',
            'id_paciente': p.id_paciente.id_paciente if p.id_paciente else None,
            'id_cita': p.id_cita.id_cita if p.id_cita else None,
            'tipo_pago': p.id_tipo_pago.nombre_tipo_pago if p.id_tipo_pago else '',
            'id_tipo_pago': p.id_tipo_pago.id_tipo_pago if p.id_tipo_pago else None,
            'monto': float(p.monto) if p.monto else 0,
            'fecha_pago': p.fecha_pago.strftime('%Y-%m-%d %H:%M') if p.fecha_pago else '',
            'referencia_pago': p.referencia_pago or '',
            'observaciones': p.observaciones or ''
        })

    paginado = _aplicar_paginacion(request, data)
    if paginado is not None:
        return JsonResponse(paginado, json_dumps_params={'ensure_ascii': False})
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def historial_citas_pagos_json(request):
    citas_qs = Citas.objects.select_related(
        'id_paciente', 'id_doctor__id_usuario', 'id_estado_cita'
    ).order_by('-fecha_cita', '-id_cita')

    # Un Doctor solo ve el historial de sus propias citas.
    if _es_doctor(request):
        doctor = _doctor_de_sesion(request)
        if not doctor:
            return JsonResponse([], safe=False, json_dumps_params={'ensure_ascii': False})
        citas_qs = citas_qs.filter(id_doctor=doctor)

    citas = list(citas_qs)

    cita_ids = [c.id_cita for c in citas]
    pagos_dict = {}
    for p in Pagos.objects.filter(id_cita__in=cita_ids).select_related('id_tipo_pago').order_by('-id_pago'):
        if p.id_cita_id not in pagos_dict:
            pagos_dict[p.id_cita_id] = p

    data = []
    for c in citas:
        paciente_nombre = ''
        if c.id_paciente:
            paciente_nombre = f"{c.id_paciente.nombres} {c.id_paciente.apellidos}"
        doctor_nombre = ''
        if c.id_doctor and c.id_doctor.id_usuario:
            u = c.id_doctor.id_usuario
            doctor_nombre = f"{u.nombres} {u.apellidos}"
        estado = c.id_estado_cita.nombre_estado if c.id_estado_cita else ''

        pago = pagos_dict.get(c.id_cita)
        if pago:
            tipo_pago = pago.id_tipo_pago.nombre_tipo_pago if pago.id_tipo_pago else 'Pendiente'
            monto = float(pago.monto) if pago.monto is not None else None
        else:
            tipo_pago = 'Pendiente'
            monto = None

        try:
            fecha_str = c.fecha_cita.strftime('%Y-%m-%d') if c.fecha_cita else ''
        except Exception:
            fecha_str = str(c.fecha_cita) if c.fecha_cita else ''

        try:
            hora_str = c.hora_inicio.strftime('%H:%M') if c.hora_inicio else ''
        except Exception:
            hora_str = str(c.hora_inicio) if c.hora_inicio else ''

        data.append({
            'id_cita': c.id_cita,
            'paciente': paciente_nombre,
            'doctor': doctor_nombre,
            'fecha_cita': fecha_str,
            'hora_inicio': hora_str,
            'estado': estado,
            'tipo_pago': tipo_pago,
            'monto': monto,
        })

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción'])
def pagos_catalogos_json(request):
    pacientes = list(
        Pacientes.objects.filter(activo=1).values(
            'id_paciente',
            'nombres',
            'apellidos'
        )
    )

    citas_qs = Citas.objects.select_related('id_paciente').order_by('-id_cita')
    citas = []

    for c in citas_qs:
        paciente = ''
        if c.id_paciente:
            paciente = f"{c.id_paciente.nombres} {c.id_paciente.apellidos}"

        citas.append({
            'id_cita': c.id_cita,
            'texto': f"Cita {c.id_cita} - {paciente} - {c.fecha_cita}"
        })

    tipos_pago = list(
        TiposPago.objects.filter(activo=1).values(
            'id_tipo_pago',
            'nombre_tipo_pago'
        )
    )

    return JsonResponse({
        'pacientes': pacientes,
        'citas': citas,
        'tipos_pago': tipos_pago
    }, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción'])
def crear_pago_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        tipo_pago = TiposPago.objects.get(id_tipo_pago=body['id_tipo_pago'])

        cita = None
        if body.get('id_cita'):
            cita = Citas.objects.get(id_cita=body['id_cita'])

        nuevo_pago = Pagos.objects.create(
            id_paciente=paciente,
            id_cita=cita,
            id_tipo_pago=tipo_pago,
            monto=body.get('monto', 0),
            fecha_pago=timezone.now(),
            referencia_pago=body.get('referencia_pago', ''),
            observaciones=body.get('observaciones', '')
        )

        registrar_auditoria(
            request.session.get('usuario_id'), 'pagos', nuevo_pago.id_pago,
            'crear', f"Pago registrado por Q{nuevo_pago.monto}"
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Pago registrado correctamente',
            'id_pago': nuevo_pago.id_pago
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def actualizar_pago_json(request, id_pago):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        pago = Pagos.objects.get(id_pago=id_pago)

        if not body.get('id_paciente'):
            return JsonResponse({'ok': False, 'error': 'El paciente es obligatorio.'}, status=400)

        if not body.get('id_tipo_pago'):
            return JsonResponse({'ok': False, 'error': 'El tipo de pago es obligatorio.'}, status=400)

        pago.id_paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        pago.id_tipo_pago = TiposPago.objects.get(id_tipo_pago=body['id_tipo_pago'])

        pago.id_cita = None
        if body.get('id_cita'):
            pago.id_cita = Citas.objects.get(id_cita=body['id_cita'])

        pago.monto = body.get('monto', 0)
        pago.referencia_pago = body.get('referencia_pago', '').strip()
        pago.observaciones = body.get('observaciones', '').strip()
        pago.save()

        registrar_auditoria(request.session.get('usuario_id'), 'pagos', pago.id_pago, 'editar', 'Pago actualizado')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Pago actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Pagos.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Pago no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def eliminar_pago_json(request, id_pago):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        pago = Pagos.objects.get(id_pago=id_pago)
        pago.delete()

        registrar_auditoria(request.session.get('usuario_id'), 'pagos', id_pago, 'eliminar', 'Pago eliminado')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Pago eliminado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Pagos.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Pago no encontrado.'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
