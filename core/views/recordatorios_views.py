from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador'])
def admin_limpiar_recordatorios(request):
    """Vista admin para ver y eliminar recordatorios manuales del dashboard."""
    TIPOS = ['manual_dashboard', 'manual_dashboard_doctor']
    placeholders = ', '.join(['%s'] * len(TIPOS))

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id_recordatorio, canal, tipo_recordatorio, destinatario, estado_envio, fecha_programada "
            f"FROM recordatorios WHERE tipo_recordatorio IN ({placeholders}) ORDER BY id_recordatorio",
            TIPOS
        )
        filas = cursor.fetchall()
        cursor.execute('SELECT COUNT(*) FROM recordatorios')
        total_bd = cursor.fetchone()[0]

    eliminados = None
    error = None
    if request.method == 'POST' and request.POST.get('confirmar') == 'si':
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'DELETE FROM recordatorios WHERE tipo_recordatorio IN ({placeholders})',
                    TIPOS
                )
                eliminados = cursor.rowcount
                cursor.execute('SELECT COUNT(*) FROM recordatorios')
                total_bd = cursor.fetchone()[0]
            filas = []
        except Exception as e:
            error = str(e)

    filas_html = ''.join(
        f'<tr><td>{escape(f[0])}</td><td>{escape(f[1])}</td><td>{escape(f[2])}</td><td>{escape(f[3])}</td><td>{escape(f[4])}</td><td>{escape(f[5])}</td></tr>'
        for f in filas
    )
    csrf_token = get_token(request)
    confirmar_btn = (
        '<form method="post" style="margin-top:20px;">'
        f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf_token}">'
        '<input type="hidden" name="confirmar" value="si">'
        f'<p><strong>{len(filas)}</strong> registros se eliminarán. Total en BD: <strong>{total_bd}</strong>. '
        f'Quedarán: <strong>{total_bd - len(filas)}</strong>.</p>'
        '<button type="submit" style="background:#fb7185;color:#fff;padding:10px 20px;border:none;border-radius:8px;cursor:pointer;font-size:14px;">'
        'CONFIRMAR BORRADO</button></form>'
    ) if filas else '<p style="color:#34d399;font-weight:700;">No hay registros manual_dashboard pendientes. BD limpia.</p>'

    ok_msg = f'<p style="color:#34d399;font-size:18px;font-weight:700;">✓ Eliminados: {eliminados}. Quedan: {total_bd} registros totales.</p>' if eliminados is not None else ''
    err_msg = f'<p style="color:#fb7185;">Error: {error}</p>' if error else ''

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
    <title>Limpiar recordatorios | Admin</title>
    <style>body{{font-family:sans-serif;padding:30px;background:#060d1b;color:#ddeeff;}}
    table{{border-collapse:collapse;width:100%;margin-top:16px;}}
    th,td{{padding:8px 12px;border:1px solid #1e3a5f;text-align:left;font-size:13px;}}
    th{{background:#0f1e36;color:#2dd4bf;}}
    tr:nth-child(even){{background:#0a1628;}}</style></head>
    <body>
    <h2>Admin — Limpiar recordatorios manual_dashboard</h2>
    {ok_msg}{err_msg}
    <table><thead><tr><th>ID</th><th>Canal</th><th>Tipo</th><th>Destinatario</th><th>Estado</th><th>Fecha programada</th></tr></thead>
    <tbody>{filas_html}</tbody></table>
    {confirmar_btn}
    <p style="margin-top:20px;"><a href="/dashboard/" style="color:#38bdf8;">← Volver al dashboard</a></p>
    </body></html>"""
    return HttpResponse(html)


@rol_requerido(['Administrador', 'Recepción'])
@require_POST
def enviar_recordatorios_correo(request):
    import traceback as _traceback
    try:
        enviados = 0
        errores = 0
        omitidos = 0
        detalle_errores = []

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id_recordatorio, destinatario, mensaje
                    FROM recordatorios
                    WHERE canal = %s
                      AND estado_envio = %s
                    ORDER BY fecha_programada ASC
                    LIMIT 50
                """, ['correo', 'pendiente'])
                recordatorios = cursor.fetchall()
        except Exception as e:
            return HttpResponse(
                f"Error consultando recordatorios de correo: {str(e)}",
                status=200,
                content_type="text/plain; charset=utf-8"
            )

        if not recordatorios:
            return HttpResponse(
                "No hay recordatorios pendientes por correo.",
                status=200,
                content_type="text/plain; charset=utf-8"
            )

        for id_recordatorio, destinatario, mensaje in recordatorios:
            if not destinatario:
                omitidos += 1
                detalle_errores.append(f"Recordatorio {id_recordatorio}: sin destinatario.")
                continue

            try:
                send_mail(
                    subject="Recordatorio de cita médica",
                    message=mensaje or "Recordatorio de cita médica.",
                    from_email=None,
                    recipient_list=[destinatario],
                    fail_silently=False,
                )

                with connection.cursor() as cursor:
                    cursor.execute("""
                        UPDATE recordatorios
                        SET estado_envio = %s
                        WHERE id_recordatorio = %s
                    """, ['enviado', id_recordatorio])

                enviados += 1

            except Exception as e:
                errores += 1
                detalle = f"Recordatorio {id_recordatorio} hacia {destinatario}: {str(e)}"
                detalle_errores.append(detalle)
                print("ERROR AL ENVIAR CORREO:", detalle)

        respuesta = f"Recordatorios procesados. Enviados: {enviados}. Omitidos: {omitidos}. Errores: {errores}."

        if detalle_errores:
            respuesta += "\n\nDetalle:\n" + "\n".join(detalle_errores[:10])

        return HttpResponse(
            respuesta,
            status=200,
            content_type="text/plain; charset=utf-8"
        )

    except Exception as e:
        return HttpResponse(
            f"Error inesperado al enviar correos: {str(e)}\n\n{_traceback.format_exc()}",
            status=200,
            content_type="text/plain; charset=utf-8"
        )


@ensure_csrf_cookie
@rol_requerido(['Administrador', 'Recepción'])
def listar_recordatorios_whatsapp(request):
    """
    Muestra WhatsApp para citas de hoy y mañana.
    Si ya existen recordatorios pendientes en la tabla recordatorios, los muestra.
    Si no existen, igual muestra enlaces manuales directos desde las citas próximas.
    """
    pendientes = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id_recordatorio, destinatario, mensaje, fecha_programada
                FROM recordatorios
                WHERE canal = %s
                  AND estado_envio = %s
                ORDER BY fecha_programada ASC
            """, ['whatsapp', 'pendiente'])
            pendientes = cursor.fetchall()
    except Exception as e:
        print('ERROR CONSULTANDO WHATSAPP PENDIENTES:', e)
        pendientes = []

    citas = list(_citas_recordatorio_qs())

    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Recordatorios WhatsApp</title>
        <style>
            body { font-family: Arial, sans-serif; background:#08111f; color:#ddeeff; padding:24px; }
            h1 { color:#ddeeff; font-size:24px; margin-bottom:8px; }
            .sub { color:#7fa0c3; margin-bottom:18px; }
            .card { background:#0f1e36; border:1px solid rgba(45,212,191,.22); border-radius:14px; padding:16px; margin-bottom:14px; }
            .numero { font-weight:bold; margin-bottom:6px; }
            .fecha { color:#93b5d9; font-size:14px; margin-bottom:8px; }
            .mensaje { background:#0a1628; padding:12px; border-radius:10px; margin-bottom:12px; white-space:pre-wrap; line-height:1.5; }
            .btn { display:inline-block; background:#22c55e; color:#04110a; text-decoration:none; padding:10px 14px; border-radius:10px; font-weight:bold; margin-right:8px; }
            button.btn { border:none; cursor:pointer; font-size:14px; font-family:inherit; }
            button.btn:disabled { opacity:.6; cursor:default; }
            .btn.secondary { background:#38bdf8; color:#06111f; }
            .empty { background:#0f1e36; border:1px solid rgba(45,212,191,.22); padding:18px; border-radius:14px; color:#cfe3ff; }
            hr { border:0; border-top:1px solid rgba(45,212,191,.18); margin:18px 0; }
        </style>
    </head>
    <body>
        <h1>Recordatorios WhatsApp</h1>
        <div class="sub">Citas de hoy y mañana. Puedes abrir WhatsApp manualmente desde cada botón.</div>
    """

    total_mostrados = 0

    if pendientes:
        html += "<h3>Pendientes generados</h3>"
        for id_recordatorio, destinatario, mensaje, fecha_programada in pendientes:
            numero_limpio = limpiar_numero_whatsapp(destinatario)
            wa_url = f"https://wa.me/{numero_limpio}?text={quote(str(mensaje))}"
            html += f"""
            <div class="card">
                <div class="numero">Número: {escape(destinatario)}</div>
                <div class="fecha">Fecha programada: {escape(fecha_programada)}</div>
                <div class="mensaje">{escape(mensaje)}</div>
                <a class="btn" target="_blank" href="{escape(wa_url)}">Abrir WhatsApp</a>
                <button type="button" class="btn secondary js-wa-abrir" data-url="/recordatorios/whatsapp/{id_recordatorio}/abrir/">Abrir y marcar enviado</button>
            </div>
            """
            total_mostrados += 1

    html += "<h3>Citas de hoy y mañana</h3>"
    for cita in citas:
        if not cita.id_paciente or not cita.id_paciente.telefono:
            continue
        mensaje = _mensaje_cita_recordatorio(cita)
        numero = cita.id_paciente.telefono
        numero_limpio = limpiar_numero_whatsapp(numero)
        wa_url = f"https://wa.me/{numero_limpio}?text={quote(str(mensaje))}"
        hora_inicio = _hora_como_time(cita.hora_inicio)
        html += f"""
        <div class="card">
            <div class="numero">Paciente: {escape(_nombre_paciente_cita(cita))} | Número: {escape(numero)}</div>
            <div class="fecha">Cita: {escape(cita.fecha_cita)} {hora_inicio.strftime('%H:%M')}</div>
            <div class="mensaje">{escape(mensaje)}</div>
            <a class="btn" target="_blank" href="{escape(wa_url)}">Enviar WhatsApp manual</a>
            <button type="button" class="btn secondary js-wa-abrir" data-url="/recordatorios/whatsapp/cita/{cita.id_cita}/abrir/">Abrir y registrar</button>
        </div>
        """
        total_mostrados += 1

    if total_mostrados == 0:
        html += '<div class="empty">No hay citas de hoy o mañana con teléfono registrado.</div>'

    html += """
        <script>
            function getCookie(name) {
                const m = document.cookie.match('(^|;)\\\\s*' + name + '\\\\s*=\\\\s*([^;]+)');
                return m ? decodeURIComponent(m.pop()) : '';
            }
            document.querySelectorAll('.js-wa-abrir').forEach(function (btn) {
                btn.addEventListener('click', async function () {
                    btn.disabled = true;
                    try {
                        const r = await fetch(btn.dataset.url, {
                            method: 'POST',
                            headers: { 'X-CSRFToken': getCookie('csrftoken') },
                            credentials: 'same-origin'
                        });
                        const data = await r.json();
                        if (data && data.ok && data.url) {
                            window.open(data.url, '_blank');
                        } else {
                            alert((data && data.error) || 'No se pudo abrir WhatsApp.');
                        }
                    } catch (e) {
                        alert('No se pudo abrir WhatsApp.');
                    } finally {
                        btn.disabled = false;
                    }
                });
            });
        </script>
    </body>
    </html>
    """

    return HttpResponse(html)


@rol_requerido(['Administrador', 'Recepción'])
@require_POST
def abrir_recordatorio_whatsapp(request, id_recordatorio):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT destinatario, mensaje
                FROM recordatorios
                WHERE id_recordatorio = %s
                  AND canal = %s
            """, [id_recordatorio, 'whatsapp'])
            recordatorio = cursor.fetchone()

        if not recordatorio:
            return JsonResponse({'ok': False, 'error': 'Recordatorio no encontrado'}, status=404)

        destinatario, mensaje = recordatorio
        numero_limpio = limpiar_numero_whatsapp(destinatario)
        mensaje_codificado = quote(str(mensaje))
        url_whatsapp = f"https://wa.me/{numero_limpio}?text={mensaje_codificado}"

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE recordatorios
                SET estado_envio = %s
                WHERE id_recordatorio = %s
            """, ['enviado', id_recordatorio])

        return JsonResponse({'ok': True, 'url': url_whatsapp})
    except Exception:
        logger.exception('Error abriendo recordatorio de WhatsApp')
        return JsonResponse({'ok': False, 'error': 'Error interno'}, status=500)


@rol_requerido(['Administrador', 'Recepción'])
@require_POST
def abrir_whatsapp_cita(request, id_cita):
    cita = get_object_or_404(
        Citas.objects.select_related('id_paciente', 'id_estado_cita'),
        id_cita=id_cita
    )

    if not cita.id_paciente or not cita.id_paciente.telefono:
        return JsonResponse(
            {'ok': False, 'error': 'La cita no tiene teléfono de paciente registrado.'},
            status=400,
        )

    mensaje = _mensaje_cita_recordatorio(cita)
    numero_limpio = limpiar_numero_whatsapp(cita.id_paciente.telefono)
    url_whatsapp = f"https://wa.me/{numero_limpio}?text={quote(str(mensaje))}"

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO recordatorios (
                    id_cita,
                    canal,
                    tipo_recordatorio,
                    destinatario,
                    mensaje,
                    fecha_programada,
                    estado_envio
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, [
                cita.id_cita,
                'whatsapp',
                'manual_dashboard',
                cita.id_paciente.telefono,
                mensaje,
                datetime.now(),
                'enviado'
            ])
    except Exception:
        logger.exception('No se pudo registrar el WhatsApp manual')

    return JsonResponse({'ok': True, 'url': url_whatsapp})


@rol_requerido(['Administrador', 'Recepción'])
@require_POST
def generar_recordatorios_automaticos(request):
    """
    Genera recordatorios manuales para citas de hoy y mañana.
    Se crean como pendientes desde ahora, para que los botones de correo/WhatsApp los encuentren de inmediato.
    """
    creados = 0
    omitidos = 0
    errores = 0

    try:
        citas = _citas_recordatorio_qs()
        fecha_programada = datetime.now()

        for cita in citas:
            try:
                if not cita.id_paciente:
                    omitidos += 1
                    continue

                mensaje = _mensaje_cita_recordatorio(cita)
                canales = [
                    ('correo', 'manual_dashboard', cita.id_paciente.correo),
                    ('whatsapp', 'manual_dashboard', cita.id_paciente.telefono),
                ]

                # Agregar recordatorio al doctor si tiene datos de contacto
                if cita.id_doctor and cita.id_doctor.id_usuario:
                    msg_doctor = _mensaje_cita_recordatorio_doctor(cita)
                    correo_doctor = cita.id_doctor.id_usuario.correo
                    tel_doctor = cita.id_doctor.id_usuario.telefono
                    if correo_doctor:
                        canales.append(('correo', 'manual_dashboard_doctor', correo_doctor))
                    if tel_doctor:
                        canales.append(('whatsapp', 'manual_dashboard_doctor', tel_doctor))
                    # Reemplazar mensaje en canales del doctor
                    canales_doctor_indices = [i for i, c in enumerate(canales) if c[1] == 'manual_dashboard_doctor']
                    for idx in canales_doctor_indices:
                        canal, tipo, dest = canales[idx]
                        canales[idx] = (canal, tipo, dest, msg_doctor)

                # Normalizar canales a tuplas de 4 elementos
                canales = [c if len(c) == 4 else (c[0], c[1], c[2], mensaje) for c in canales]

                for canal, tipo, destinatario, msg in canales:
                    if not destinatario:
                        omitidos += 1
                        continue

                    with connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*)
                            FROM recordatorios
                            WHERE id_cita = %s
                              AND canal = %s
                              AND tipo_recordatorio = %s
                              AND estado_envio = %s
                        """, [cita.id_cita, canal, tipo, 'pendiente'])
                        existe = cursor.fetchone()[0]

                    if existe:
                        omitidos += 1
                        continue

                    with connection.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO recordatorios (
                                id_cita,
                                canal,
                                tipo_recordatorio,
                                destinatario,
                                mensaje,
                                fecha_programada,
                                estado_envio
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, [
                            cita.id_cita,
                            canal,
                            tipo,
                            destinatario,
                            msg,
                            fecha_programada,
                            'pendiente'
                        ])

                    creados += 1

            except Exception as e:
                errores += 1
                print('ERROR GENERANDO RECORDATORIO:', e)

        return HttpResponse(
            f"Recordatorios generados. Creados: {creados}. Omitidos: {omitidos}. Errores: {errores}."
        )

    except Exception as e:
        return HttpResponse(f"Error al generar recordatorios: {str(e)}", status=500)
