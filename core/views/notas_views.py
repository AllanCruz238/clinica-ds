from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador', 'Doctor'])
@ensure_csrf_cookie
def notas_page(request):
    return render(request, 'core/notas.html')


@rol_requerido(['Administrador', 'Doctor'])
def notas_json(request):
    notas = NotasClinicas.objects.select_related(
        'id_paciente',
        'id_cita',
        'id_doctor__id_usuario'
    ).order_by('-id_nota_clinica')

    # Un Doctor solo ve sus propias notas.
    if _es_doctor(request):
        doctor = _doctor_de_sesion(request)
        if not doctor:
            return JsonResponse([], safe=False, json_dumps_params={'ensure_ascii': False})
        notas = notas.filter(id_doctor=doctor)

    data = []

    for n in notas:
        doctor = ''
        if n.id_doctor and n.id_doctor.id_usuario:
            doctor = f"{n.id_doctor.id_usuario.nombres} {n.id_doctor.id_usuario.apellidos}"

        data.append({
            'id_nota_clinica': n.id_nota_clinica,
            'id_paciente': n.id_paciente.id_paciente if n.id_paciente else None,
            'paciente': f"{n.id_paciente.nombres} {n.id_paciente.apellidos}" if n.id_paciente else '',
            'id_cita': n.id_cita.id_cita if n.id_cita else None,
            'id_doctor': n.id_doctor.id_doctor if n.id_doctor else None,
            'doctor': doctor,
            'titulo': n.titulo or '',
            'contenido': n.contenido or '',
            'recomendaciones': n.recomendaciones or '',
            'fecha_nota': n.fecha_nota.strftime('%Y-%m-%d %H:%M') if n.fecha_nota else ''
        })

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Doctor'])
def notas_catalogos_json(request):
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
            'id_paciente': c.id_paciente.id_paciente if c.id_paciente else None,
            'texto': f"Cita {c.id_cita} - {paciente} - {c.fecha_cita}"
        })

    doctores_qs = Doctores.objects.select_related('id_usuario').filter(activo=1)
    doctores = []

    for d in doctores_qs:
        nombre = 'Doctor'
        if d.id_usuario:
            nombre = f"{d.id_usuario.nombres} {d.id_usuario.apellidos}"

        doctores.append({
            'id_doctor': d.id_doctor,
            'nombre': nombre
        })

    return JsonResponse({
        'pacientes': pacientes,
        'citas': citas,
        'doctores': doctores
    }, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Doctor'])
def crear_nota_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        doctor = Doctores.objects.get(id_doctor=body['id_doctor'])

        cita = None
        if body.get('id_cita'):
            cita = Citas.objects.get(id_cita=body['id_cita'])

        nueva_nota = NotasClinicas.objects.create(
            id_paciente=paciente,
            id_cita=cita,
            id_doctor=doctor,
            titulo=body.get('titulo', ''),
            contenido=body.get('contenido', ''),
            recomendaciones=body.get('recomendaciones', ''),
            fecha_nota=timezone.now()
        )

        registrar_auditoria(
            request.session.get('usuario_id'), 'notas_clinicas', nueva_nota.id_nota_clinica,
            'crear', f"Nota clínica creada para paciente {paciente.id_paciente}"
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Nota clínica guardada correctamente',
            'id_nota_clinica': nueva_nota.id_nota_clinica
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
