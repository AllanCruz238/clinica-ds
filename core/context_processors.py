def rol_actual(request):
    """Expone el rol y el nombre del usuario en sesión a todas las plantillas,
    para mostrar/ocultar enlaces del menú según el rol."""
    return {
        'rol': request.session.get('rol', ''),
        'nombre_usuario': request.session.get('nombre_usuario', ''),
    }
