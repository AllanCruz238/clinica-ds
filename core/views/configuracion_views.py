from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador'])
@ensure_csrf_cookie
def configuracion_page(request):
    return render(request, 'core/configuracion.html')


@rol_requerido(['Administrador'])
def configuracion_json(request):
    config = ConfiguracionClinica.objects.filter(activo=1).first()

    if not config:
        return JsonResponse({
            'ok': False,
            'error': 'No hay configuración registrada'
        }, status=404)

    data = {
        'id_configuracion': config.id_configuracion,
        'nombre_clinica': config.nombre_clinica or '',
        'slogan': config.slogan or '',
        'direccion': config.direccion or '',
        'telefono': config.telefono or '',
        'correo': config.correo or '',
        'sitio_web': config.sitio_web or '',
        'logo_url': config.logo_url or '',
        'color_primario': config.color_primario or '#38bdf8',
        'color_secundario': config.color_secundario or '#0f172a',
        'fecha_actualizacion': config.fecha_actualizacion.strftime('%Y-%m-%d %H:%M') if config.fecha_actualizacion else ''
    }

    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador'])
def actualizar_configuracion_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        config = ConfiguracionClinica.objects.filter(activo=1).first()

        if not config:
            config = ConfiguracionClinica.objects.create(
                nombre_clinica='Clínica DS',
                activo=1
            )

        config.nombre_clinica = body.get('nombre_clinica', '')
        config.slogan = body.get('slogan', '')
        config.direccion = body.get('direccion', '')
        config.telefono = body.get('telefono', '')
        config.correo = body.get('correo', '')
        config.sitio_web = body.get('sitio_web', '')
        config.logo_url = body.get('logo_url', '')
        config.color_primario = body.get('color_primario', '#38bdf8')
        config.color_secundario = body.get('color_secundario', '#0f172a')

        config.save()

        registrar_auditoria(request.session.get('usuario_id'), 'configuracion_clinica', config.id_configuracion, 'editar', 'Configuración actualizada')

        return JsonResponse({
            'ok': True,
            'mensaje': 'Configuración actualizada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
