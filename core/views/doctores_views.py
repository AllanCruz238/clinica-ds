from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador'])
@ensure_csrf_cookie
def doctores_page(request):
    return render(request, 'core/doctores.html')


@rol_requerido(['Administrador'])
def doctores_json(request):
    doctores = Doctores.objects.select_related(
        'id_usuario',
        'id_especialidad'
    ).order_by('-id_doctor')

    data = []

    for d in doctores:
        data.append({
            'id_doctor': d.id_doctor,
            'id_usuario': d.id_usuario.id_usuario if d.id_usuario else None,
            'doctor': f"{d.id_usuario.nombres} {d.id_usuario.apellidos}" if d.id_usuario else '',
            'correo': d.id_usuario.correo if d.id_usuario else '',
            'telefono': d.id_usuario.telefono if d.id_usuario else '',
            'id_especialidad': d.id_especialidad.id_especialidad if d.id_especialidad else None,
            'especialidad': d.id_especialidad.nombre_especialidad if d.id_especialidad else '',
            'numero_colegiado': d.numero_colegiado or '',
            'duracion_cita_minutos': d.duracion_cita_minutos or 60,
            'color_agenda': d.color_agenda or '#38bdf8',
            'activo': d.activo
        })

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def doctores_catalogos_json(request):
    usuarios = list(
        Usuarios.objects.filter(activo=1).values(
            'id_usuario',
            'username',
            'nombres',
            'apellidos',
            'correo',
            'telefono'
        )
    )

    especialidades = list(
        Especialidades.objects.filter(activo=1).order_by('nombre_especialidad').values(
            'id_especialidad',
            'nombre_especialidad'
        )
    )

    usuarios_ya_doctores = list(
        Doctores.objects.filter(activo=1).values_list('id_usuario_id', flat=True)
    )

    return JsonResponse({
        'usuarios': usuarios,
        'especialidades': especialidades,
        'usuarios_ya_doctores': usuarios_ya_doctores
    }, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def crear_doctor_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        usuario = Usuarios.objects.get(id_usuario=body['id_usuario'])

        especialidad_custom = (body.get('especialidad_custom') or '').strip()
        if especialidad_custom:
            especialidad, _ = Especialidades.objects.get_or_create(
                nombre_especialidad=especialidad_custom,
                defaults={'activo': 1}
            )
        else:
            especialidad = Especialidades.objects.get(id_especialidad=body['id_especialidad'])

        correo = body.get('correo', '').strip()
        if correo and Usuarios.objects.filter(correo=correo).exclude(id_usuario=usuario.id_usuario).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado en otro usuario.'}, status=400)

        if body.get('nombres') is not None:
            usuario.nombres = body.get('nombres', '').strip()
        if body.get('apellidos') is not None:
            usuario.apellidos = body.get('apellidos', '').strip()
        if body.get('correo') is not None:
            usuario.correo = correo
        if body.get('telefono') is not None:
            usuario.telefono = body.get('telefono', '').strip()
        usuario.save()

        nuevo_doctor = Doctores.objects.create(
            id_usuario=usuario,
            id_especialidad=especialidad,
            numero_colegiado=body.get('numero_colegiado', ''),
            duracion_cita_minutos=60,
            color_agenda=body.get('color_agenda', '#38bdf8'),
            activo=1
        )

        registrar_auditoria(
            request.session.get('usuario_id'), 'doctores', nuevo_doctor.id_doctor,
            'crear', f"Doctor creado para usuario {usuario.username}"
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Doctor creado correctamente',
            'id_doctor': nuevo_doctor.id_doctor
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def actualizar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        doctor = Doctores.objects.select_related('id_usuario', 'id_especialidad').get(id_doctor=id_doctor)
        usuario = Usuarios.objects.get(id_usuario=body['id_usuario'])

        especialidad_custom = (body.get('especialidad_custom') or '').strip()
        if especialidad_custom:
            especialidad, _ = Especialidades.objects.get_or_create(
                nombre_especialidad=especialidad_custom,
                defaults={'activo': 1}
            )
        else:
            especialidad = Especialidades.objects.get(id_especialidad=body['id_especialidad'])

        correo = body.get('correo', '').strip()
        if correo and Usuarios.objects.filter(correo=correo).exclude(id_usuario=usuario.id_usuario).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado en otro usuario.'}, status=400)

        usuario.nombres = body.get('nombres', usuario.nombres or '').strip()
        usuario.apellidos = body.get('apellidos', usuario.apellidos or '').strip()
        usuario.correo = correo
        usuario.telefono = body.get('telefono', usuario.telefono or '').strip()
        usuario.save()

        doctor.id_usuario = usuario
        doctor.id_especialidad = especialidad
        doctor.numero_colegiado = body.get('numero_colegiado', '').strip()
        doctor.color_agenda = body.get('color_agenda', '#38bdf8') or '#38bdf8'
        doctor.activo = int(body.get('activo', doctor.activo if doctor.activo is not None else 1))
        if not doctor.duracion_cita_minutos:
            doctor.duracion_cita_minutos = 60
        doctor.save()

        registrar_auditoria(request.session.get('usuario_id'), 'doctores', doctor.id_doctor, 'editar', 'Doctor actualizado')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Doctor actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def desactivar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        doctor = Doctores.objects.get(id_doctor=id_doctor)
        doctor.activo = 0
        doctor.save()

        registrar_auditoria(request.session.get('usuario_id'), 'doctores', doctor.id_doctor, 'desactivar', 'Doctor desactivado')

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def activar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        doctor = Doctores.objects.get(id_doctor=id_doctor)
        doctor.activo = 1
        doctor.save()

        registrar_auditoria(request.session.get('usuario_id'), 'doctores', doctor.id_doctor, 'activar', 'Doctor activado')

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
