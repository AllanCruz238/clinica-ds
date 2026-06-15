from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
@ensure_csrf_cookie
def citas_page(request):
    return render(request, 'core/citas.html')


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def citas_json(request):
    citas = Citas.objects.select_related(
        'id_paciente',
        'id_doctor__id_usuario',
        'id_estado_cita',
        'id_motivo_consulta'
    )

    # Un Doctor solo ve sus propias citas.
    if _es_doctor(request):
        doctor = _doctor_de_sesion(request)
        if not doctor:
            return JsonResponse([], safe=False, json_dumps_params={'ensure_ascii': False})
        citas = citas.filter(id_doctor=doctor)

    eventos = []

    for c in citas:
        paciente = f"{c.id_paciente.nombres} {c.id_paciente.apellidos}" if c.id_paciente else "Paciente"

        doctor = ""
        if c.id_doctor and c.id_doctor.id_usuario:
            doctor = f"{c.id_doctor.id_usuario.nombres} {c.id_doctor.id_usuario.apellidos}"

        estado = c.id_estado_cita.nombre_estado if c.id_estado_cita else "Sin estado"
        motivo = c.id_motivo_consulta.nombre_motivo if c.id_motivo_consulta else ""

        color = '#3b82f6'
        if estado.lower() == 'confirmada':
            color = '#22c55e'
        elif estado.lower() == 'cancelada':
            color = '#ef4444'
        elif estado.lower() == 'pendiente':
            color = '#f59e0b'
        elif estado.lower() == 'no-show':
            color = '#6b7280'
        elif estado.lower() == 'completada':
            color = '#2563eb'

        start = None
        end = None

        if c.fecha_cita and c.hora_inicio:
            start = f"{c.fecha_cita}T{c.hora_inicio}"

        if c.fecha_cita and c.hora_fin:
            end = f"{c.fecha_cita}T{c.hora_fin}"

        eventos.append({
            "id": c.id_cita,
            "title": paciente,
            "start": start,
            "end": end,
            "backgroundColor": color,
            "borderColor": color,
            "extendedProps": {
                "doctor": doctor,
                "estado": estado,
                "motivo": motivo,
                "modalidad": c.modalidad or "",
                "detalle": c.razon_consulta_detalle or "",
                "observaciones": c.observaciones or "",
                "id_paciente": c.id_paciente.id_paciente if c.id_paciente else '',
                "id_doctor": c.id_doctor.id_doctor if c.id_doctor else '',
                "id_estado_cita": c.id_estado_cita.id_estado_cita if c.id_estado_cita else '',
                "id_motivo_consulta": c.id_motivo_consulta.id_motivo_consulta if c.id_motivo_consulta else '',
                "link_jitsi": f"https://meet.jit.si/ClinicaDS-{c.id_cita}" if (c.modalidad or '').lower() == 'virtual' else ''
            }
        })

    return JsonResponse(eventos, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def catalogos_citas_json(request):
    pacientes = list(
        Pacientes.objects.filter(activo=1).values(
            'id_paciente',
            'nombres',
            'apellidos'
        )
    )

    doctores_qs = Doctores.objects.select_related('id_usuario').filter(activo=1)
    doctores = []

    for d in doctores_qs:
        nombre = "Doctor"
        if d.id_usuario:
            nombre = f"{d.id_usuario.nombres} {d.id_usuario.apellidos}"

        doctores.append({
            'id_doctor': d.id_doctor,
            'nombre': nombre
        })

    estados = list(
        EstadosCita.objects.filter(activo=1).values(
            'id_estado_cita',
            'nombre_estado'
        )
    )

    motivos = list(
        MotivosConsulta.objects.filter(activo=1).values(
            'id_motivo_consulta',
            'nombre_motivo'
        )
    )

    return JsonResponse({
        'pacientes': pacientes,
        'doctores': doctores,
        'estados': estados,
        'motivos': motivos
    }, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción'])
def crear_cita_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        doctor = Doctores.objects.get(id_doctor=body['id_doctor'])
        estado = EstadosCita.objects.get(id_estado_cita=body['id_estado_cita'])
        id_motivo = body.get('id_motivo_consulta', '')
        if str(id_motivo) == 'otro' or not id_motivo:
            motivo, _ = MotivosConsulta.objects.get_or_create(nombre_motivo='Otro')
        else:
            motivo = MotivosConsulta.objects.get(id_motivo_consulta=id_motivo)
        creado_por = Usuarios.objects.get(id_usuario=request.session.get('usuario_id'))

        try:
            from zoneinfo import ZoneInfo
            ahora_gt = datetime.now(ZoneInfo('America/Guatemala')).replace(tzinfo=None)
        except Exception:
            ahora_gt = datetime.now()

        fecha_cita_val = date.fromisoformat(body['fecha_cita'])
        hora_parts = body['hora_inicio'].split(':')
        hora_inicio_val = time(int(hora_parts[0]), int(hora_parts[1]))
        dt_cita = datetime.combine(fecha_cita_val, hora_inicio_val)

        if dt_cita < ahora_gt:
            estados_permitidos = {'cancelada', 'no asistió', 'no asistio'}
            if estado.nombre_estado.lower() not in estados_permitidos:
                return JsonResponse({
                    'ok': False,
                    'error': 'Las citas en fechas u horas pasadas solo pueden guardarse con estado Cancelada o No asistió.'
                }, status=400)

        # Evitar choques con otra cita del mismo doctor (salvo si esta es Cancelada).
        if estado.nombre_estado.lower() not in {'cancelada', 'cancelado'}:
            hora_fin_val = _hora_como_time(body.get('hora_fin'))
            if _hay_choque_citas(doctor, fecha_cita_val, hora_inicio_val, hora_fin_val):
                return JsonResponse({
                    'ok': False,
                    'error': 'El doctor ya tiene otra cita que se solapa con ese horario.'
                }, status=400)

        nueva_cita = Citas.objects.create(
            id_paciente=paciente,
            id_doctor=doctor,
            id_estado_cita=estado,
            id_motivo_consulta=motivo,
            fecha_cita=body['fecha_cita'],
            hora_inicio=body['hora_inicio'],
            hora_fin=body['hora_fin'],
            modalidad=body.get('modalidad', ''),
            razon_consulta_detalle=body.get('razon_consulta_detalle', ''),
            observaciones=body.get('observaciones', ''),
            creada_por=creado_por
        )

        link_jitsi = ''
        if (body.get('modalidad') or '').lower() == 'virtual':
            link_jitsi = f"https://meet.jit.si/ClinicaDS-{nueva_cita.id_cita}"

        registrar_auditoria(
            request.session.get('usuario_id'), 'citas', nueva_cita.id_cita,
            'crear', f"Cita creada para {fecha_cita_val} {body.get('hora_inicio', '')}"
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita creada correctamente',
            'id_cita': nueva_cita.id_cita,
            'link_jitsi': link_jitsi
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def editar_cita_json(request, id_cita):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        cita = Citas.objects.get(id_cita=id_cita)
        nuevo_estado = EstadosCita.objects.get(id_estado_cita=body['id_estado_cita'])

        try:
            from zoneinfo import ZoneInfo
            ahora_gt = datetime.now(ZoneInfo('America/Guatemala')).replace(tzinfo=None)
        except Exception:
            ahora_gt = datetime.now()

        fecha_cita_val = date.fromisoformat(body['fecha_cita'])
        hora_parts = body['hora_inicio'].split(':')
        hora_inicio_val = time(int(hora_parts[0]), int(hora_parts[1]))
        dt_cita = datetime.combine(fecha_cita_val, hora_inicio_val)

        if dt_cita < ahora_gt:
            estados_permitidos = {'cancelada', 'no asistió', 'no asistio'}
            if nuevo_estado.nombre_estado.lower() not in estados_permitidos:
                return JsonResponse({
                    'ok': False,
                    'error': 'Las citas en fechas u horas pasadas solo pueden tener estado Cancelada o No asistió.'
                }, status=400)

        doctor_edit = Doctores.objects.get(id_doctor=body['id_doctor'])

        # Evitar choques con otra cita del mismo doctor (salvo si esta es Cancelada).
        if nuevo_estado.nombre_estado.lower() not in {'cancelada', 'cancelado'}:
            hora_fin_val = _hora_como_time(body.get('hora_fin'))
            if _hay_choque_citas(doctor_edit, fecha_cita_val, hora_inicio_val, hora_fin_val, excluir_id=cita.id_cita):
                return JsonResponse({
                    'ok': False,
                    'error': 'El doctor ya tiene otra cita que se solapa con ese horario.'
                }, status=400)

        cita.id_paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        cita.id_doctor = doctor_edit
        cita.id_estado_cita = nuevo_estado
        id_motivo_edit = body.get('id_motivo_consulta', '')
        if str(id_motivo_edit) == 'otro' or not id_motivo_edit:
            cita.id_motivo_consulta, _ = MotivosConsulta.objects.get_or_create(nombre_motivo='Otro')
        else:
            cita.id_motivo_consulta = MotivosConsulta.objects.get(id_motivo_consulta=id_motivo_edit)
        cita.fecha_cita = body['fecha_cita']
        cita.hora_inicio = body['hora_inicio']
        cita.hora_fin = body['hora_fin']
        cita.modalidad = body.get('modalidad', '')
        cita.razon_consulta_detalle = body.get('razon_consulta_detalle', '')
        cita.observaciones = body.get('observaciones', '')
        cita.save()

        registrar_auditoria(request.session.get('usuario_id'), 'citas', cita.id_cita, 'editar', 'Cita actualizada')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita actualizada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


actualizar_cita_json = editar_cita_json


@rol_requerido(['Administrador', 'Recepción'])
def cancelar_cita_json(request, id_cita):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        cita = Citas.objects.get(id_cita=id_cita)
        estado_cancelada = EstadosCita.objects.get(nombre_estado__iexact='Cancelada')
        cita.id_estado_cita = estado_cancelada
        cita.save()

        registrar_auditoria(request.session.get('usuario_id'), 'citas', cita.id_cita, 'cancelar', 'Cita cancelada')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita cancelada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def descartar_pendiente_pago(request, id_cita):
    """Marca la cita como 'No asistió' para sacarla del listado de pendientes de pago."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)
    try:
        cita = Citas.objects.get(id_cita=id_cita)
        estado_no_asistio = EstadosCita.objects.filter(
            nombre_estado__iexact='No asistió'
        ).first() or EstadosCita.objects.filter(
            nombre_estado__iexact='No asistio'
        ).first()
        if not estado_no_asistio:
            return JsonResponse({'ok': False, 'error': 'No existe el estado "No asistió" en la base de datos.'}, status=400)
        cita.id_estado_cita = estado_no_asistio
        cita.save()
        return JsonResponse({'ok': True})
    except Citas.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Cita no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
