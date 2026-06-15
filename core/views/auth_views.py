from .common import *  # noqa: F401,F403


@ensure_csrf_cookie
def login_page(request):
    if request.session.get('usuario_id'):
        return redirect('/dashboard/')
    return render(request, 'core/login.html')


def login_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        username = body.get('username', '').strip()
        password = body.get('password', '').strip()

        ip = _client_ip(request)
        cache_key = f"login_intentos:{ip}:{username.lower()}"
        intentos = cache.get(cache_key, 0)

        if intentos >= MAX_INTENTOS_LOGIN:
            logger.warning('Login bloqueado por fuerza bruta: usuario "%s" desde %s', username, ip)
            return JsonResponse(
                {'ok': False, 'error': 'Demasiados intentos fallidos. Intenta de nuevo en unos minutos.'},
                status=429,
            )

        usuario = Usuarios.objects.select_related('id_rol').filter(
            username=username,
            activo=1
        ).first()

        if usuario:
            credenciales_validas = check_password(password, usuario.password_hash)
        else:
            # Ejecutamos un check_password "señuelo" para que el tiempo de
            # respuesta sea similar al de un usuario existente.
            check_password(password, _DUMMY_PASSWORD_HASH)
            credenciales_validas = False

        if not credenciales_validas:
            cache.set(cache_key, intentos + 1, BLOQUEO_LOGIN_SEGUNDOS)
            logger.warning('Intento de login fallido para "%s" desde %s', username, ip)
            # Mismo mensaje para usuario inexistente y contraseña incorrecta.
            return JsonResponse(
                {'ok': False, 'error': 'Usuario o contraseña incorrectos'},
                status=401,
            )

        # Login correcto: limpiamos el contador de intentos.
        cache.delete(cache_key)

        usuario.ultimo_acceso = timezone.now()
        usuario.save()

        request.session['usuario_id'] = usuario.id_usuario
        request.session['username'] = usuario.username
        request.session['nombre_usuario'] = f"{usuario.nombres or ''} {usuario.apellidos or ''}".strip()
        request.session['rol'] = usuario.id_rol.nombre_rol if usuario.id_rol else ''

        return JsonResponse({
            'ok': True,
            'mensaje': 'Login correcto',
            'redirect': '/dashboard/'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception:
        logger.exception('Error en login_json')
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=400)


def logout_view(request):
    request.session.flush()
    return redirect('/login/')
