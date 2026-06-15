from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador'])
@ensure_csrf_cookie
def usuarios_page(request):
    return render(request, 'core/usuarios.html')


@rol_requerido(['Administrador'])
def usuarios_json(request):
    usuarios = Usuarios.objects.select_related('id_rol').order_by('-id_usuario')

    busqueda = request.GET.get('search', '').strip()
    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda)
            | Q(nombres__icontains=busqueda)
            | Q(apellidos__icontains=busqueda)
            | Q(correo__icontains=busqueda)
        )

    data = []

    for u in usuarios:
        data.append({
            'id_usuario': u.id_usuario,
            'id_rol': u.id_rol.id_rol if u.id_rol else None,
            'rol': u.id_rol.nombre_rol if u.id_rol else '',
            'username': u.username,
            'correo': u.correo or '',
            'telefono': u.telefono or '',
            'nombres': u.nombres or '',
            'apellidos': u.apellidos or '',
            'activo': u.activo,
            'fecha_creacion': u.fecha_creacion.strftime('%Y-%m-%d %H:%M') if u.fecha_creacion else '',
            'ultimo_acceso': u.ultimo_acceso.strftime('%Y-%m-%d %H:%M') if u.ultimo_acceso else ''
        })

    paginado = _aplicar_paginacion(request, data)
    if paginado is not None:
        return JsonResponse(paginado, json_dumps_params={'ensure_ascii': False})
    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def usuarios_catalogos_json(request):
    roles = list(
        Roles.objects.filter(activo=1).values(
            'id_rol',
            'nombre_rol'
        )
    )

    return JsonResponse({'roles': roles}, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def crear_usuario_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        username = body.get('username', '').strip()
        password = body.get('password', '').strip()
        correo = body.get('correo', '').strip()

        if not username or not password:
            return JsonResponse({'ok': False, 'error': 'Usuario y contraseña son obligatorios.'}, status=400)

        if Usuarios.objects.filter(username=username).exists():
            return JsonResponse({'ok': False, 'error': 'El nombre de usuario ya existe.'}, status=400)

        if correo and Usuarios.objects.filter(correo=correo).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado.'}, status=400)

        rol = Roles.objects.get(id_rol=body['id_rol'])

        nuevo_usuario = Usuarios.objects.create(
            id_rol=rol,
            username=username,
            password_hash=make_password(password),
            correo=correo,
            telefono=body.get('telefono', '').strip(),
            nombres=body.get('nombres', '').strip(),
            apellidos=body.get('apellidos', '').strip(),
            activo=1,
            fecha_creacion=timezone.now()
        )

        registrar_auditoria(
            request.session.get('usuario_id'), 'usuarios', nuevo_usuario.id_usuario,
            'crear', f"Usuario creado: {nuevo_usuario.username}"
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario creado correctamente',
            'id_usuario': nuevo_usuario.id_usuario
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def actualizar_usuario_json(request, id_usuario):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        usuario = Usuarios.objects.get(id_usuario=id_usuario)
        rol = Roles.objects.get(id_rol=body['id_rol'])

        username = body.get('username', '').strip()
        correo = body.get('correo', '').strip()

        if Usuarios.objects.filter(username=username).exclude(id_usuario=id_usuario).exists():
            return JsonResponse({'ok': False, 'error': 'El nombre de usuario ya existe.'}, status=400)

        if correo and Usuarios.objects.filter(correo=correo).exclude(id_usuario=id_usuario).exists():
            return JsonResponse({'ok': False, 'error': 'El correo ya está registrado.'}, status=400)

        usuario.id_rol = rol
        usuario.username = username
        usuario.correo = correo
        usuario.telefono = body.get('telefono', '').strip()
        usuario.nombres = body.get('nombres', '').strip()
        usuario.apellidos = body.get('apellidos', '').strip()

        nueva_password = body.get('password', '').strip()
        if nueva_password:
            usuario.password_hash = make_password(nueva_password)

        usuario.save()

        registrar_auditoria(request.session.get('usuario_id'), 'usuarios', usuario.id_usuario, 'editar', f"Usuario actualizado: {usuario.username}")

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def desactivar_usuario_json(request, id_usuario):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        usuario = Usuarios.objects.get(id_usuario=id_usuario)

        if usuario.id_usuario == request.session.get('usuario_id'):
            return JsonResponse({'ok': False, 'error': 'No puedes desactivar tu propio usuario.'}, status=400)

        usuario.activo = 0
        usuario.save()

        registrar_auditoria(request.session.get('usuario_id'), 'usuarios', usuario.id_usuario, 'desactivar', f"Usuario desactivado: {usuario.username}")

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario desactivado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def activar_usuario_json(request, id_usuario):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        usuario = Usuarios.objects.get(id_usuario=id_usuario)
        usuario.activo = 1
        usuario.save()

        registrar_auditoria(request.session.get('usuario_id'), 'usuarios', usuario.id_usuario, 'activar', f"Usuario activado: {usuario.username}")

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario activado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
@ensure_csrf_cookie
def roles_page(request):
    return render(request, 'core/roles.html')


@rol_requerido(['Administrador'])
def roles_json(request):
    roles = Roles.objects.all().order_by('-id_rol')

    data = []

    for r in roles:
        cantidad_usuarios = Usuarios.objects.filter(id_rol=r.id_rol).count()

        data.append({
            'id_rol': r.id_rol,
            'nombre_rol': r.nombre_rol,
            'descripcion': r.descripcion or '',
            'activo': r.activo,
            'cantidad_usuarios': cantidad_usuarios
        })

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def crear_rol_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)
        nombre_rol = body.get('nombre_rol', '').strip()

        if not nombre_rol:
            return JsonResponse({'ok': False, 'error': 'El nombre del rol es obligatorio.'}, status=400)

        if Roles.objects.filter(nombre_rol=nombre_rol).exists():
            return JsonResponse({'ok': False, 'error': 'Ese rol ya existe.'}, status=400)

        nuevo_rol = Roles.objects.create(
            nombre_rol=nombre_rol,
            descripcion=body.get('descripcion', '').strip(),
            activo=1
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Rol creado correctamente',
            'id_rol': nuevo_rol.id_rol
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def actualizar_rol_json(request, id_rol):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        rol = Roles.objects.get(id_rol=id_rol)
        nombre_rol = body.get('nombre_rol', '').strip()

        if not nombre_rol:
            return JsonResponse({'ok': False, 'error': 'El nombre del rol es obligatorio.'}, status=400)

        if Roles.objects.filter(nombre_rol=nombre_rol).exclude(id_rol=id_rol).exists():
            return JsonResponse({'ok': False, 'error': 'Ese rol ya existe.'}, status=400)

        rol.nombre_rol = nombre_rol
        rol.descripcion = body.get('descripcion', '').strip()
        rol.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Rol actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def desactivar_rol_json(request, id_rol):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        rol = Roles.objects.get(id_rol=id_rol)

        usuarios_activos = Usuarios.objects.filter(id_rol=rol, activo=1).count()

        if usuarios_activos > 0:
            return JsonResponse({
                'ok': False,
                'error': 'No puedes desactivar un rol con usuarios activos.'
            }, status=400)

        rol.activo = 0
        rol.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Rol desactivado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def activar_rol_json(request, id_rol):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        rol = Roles.objects.get(id_rol=id_rol)
        rol.activo = 1
        rol.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Rol activado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
