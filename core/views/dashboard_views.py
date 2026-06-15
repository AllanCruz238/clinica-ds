from .common import *  # noqa: F401,F403


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
@ensure_csrf_cookie
def dashboard_page(request):
    return render(request, 'core/dashboard.html')


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def dashboard_json(request):
    hoy = date.today()
    hace_7_dias = hoy - timedelta(days=7)

    citas_hoy = Citas.objects.filter(fecha_cita=hoy).count()

    ingresos_semanales = Pagos.objects.filter(
        fecha_pago__date__gte=hace_7_dias,
        fecha_pago__date__lte=hoy
    ).aggregate(total=Sum('monto'))['total'] or 0

    total_citas = Citas.objects.count()
    canceladas = Citas.objects.filter(id_estado_cita__nombre_estado__iexact='Cancelada').count()
    tasa_cancelaciones = round((canceladas / total_citas) * 100, 2) if total_citas > 0 else 0

    data = {
        'citas_hoy': citas_hoy,
        'pacientes_con_deuda': 0,
        'ingresos_semanales': float(ingresos_semanales),
        'tasa_cancelaciones': tasa_cancelaciones
    }

    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def api_dashboard_recordatorios(request):
    """
    Dashboard para producción en Render/PostgreSQL.
    No usa funciones MySQL como CURDATE(), DATE_ADD(), MONTH() o YEAR().
    """
    try:
        from decimal import Decimal
        from zoneinfo import ZoneInfo

        def to_float(value):
            if value is None:
                return 0.0
            if isinstance(value, Decimal):
                return float(value)
            try:
                return float(value)
            except Exception:
                return 0.0

        def estado_no_cancelado(qs):
            return qs.exclude(id_estado_cita__nombre_estado__iexact='Cancelada').exclude(
                id_estado_cita__nombre_estado__iexact='Cancelado'
            )

        def nombre_paciente(paciente):
            if not paciente:
                return ''
            return f"{paciente.nombres or ''} {paciente.apellidos or ''}".strip()

        def nombre_doctor(doctor):
            if not doctor or not doctor.id_usuario:
                return ''
            return f"{doctor.id_usuario.nombres or ''} {doctor.id_usuario.apellidos or ''}".strip()

        try:
            ahora_gt = datetime.now(ZoneInfo("America/Guatemala"))
        except Exception:
            ahora_gt = datetime.now()
        hoy = ahora_gt.date()
        hace_7_dias_dt = datetime.now() - timedelta(days=7)
        fin_7_dias = hoy + timedelta(days=7)

        citas_base = Citas.objects.select_related(
            'id_paciente',
            'id_doctor__id_usuario',
            'id_estado_cita'
        )

        citas_validas = estado_no_cancelado(citas_base)

        pagos_base = Pagos.objects.select_related(
            'id_paciente',
            'id_cita',
            'id_tipo_pago'
        )

        pagos_mes_qs = pagos_base.filter(
            fecha_pago__isnull=False,
            fecha_pago__year=hoy.year,
            fecha_pago__month=hoy.month
        )

        ingresos_semanales = pagos_base.filter(
            fecha_pago__isnull=False,
            fecha_pago__gte=hace_7_dias_dt
        ).aggregate(total=Sum('monto'))['total'] or 0

        ingresos_mes = pagos_mes_qs.aggregate(total=Sum('monto'))['total'] or 0

        ultimo_pago_obj = pagos_base.order_by('-fecha_pago', '-id_pago').first()
        ultimo_pago = to_float(ultimo_pago_obj.monto) if ultimo_pago_obj else 0

        total_citas_mes = citas_base.filter(
            fecha_cita__isnull=False,
            fecha_cita__year=hoy.year,
            fecha_cita__month=hoy.month
        ).count()

        canceladas_mes = citas_base.filter(
            fecha_cita__isnull=False,
            fecha_cita__year=hoy.year,
            fecha_cita__month=hoy.month,
            id_estado_cita__nombre_estado__iexact='Cancelada'
        ).count() + citas_base.filter(
            fecha_cita__isnull=False,
            fecha_cita__year=hoy.year,
            fecha_cita__month=hoy.month,
            id_estado_cita__nombre_estado__iexact='Cancelado'
        ).count()

        tasa_cancelaciones = round((canceladas_mes / total_citas_mes) * 100, 2) if total_citas_mes else 0

        citas_con_pago_ids = list(
            Pagos.objects.exclude(id_cita__isnull=True).values_list('id_cita_id', flat=True)
        )

        citas_pasadas_sin_pago = estado_no_cancelado(
            citas_base.filter(fecha_cita__lt=hoy)
        ).exclude(id_cita__in=citas_con_pago_ids).exclude(
            id_estado_cita__nombre_estado__iexact='No asistió'
        ).exclude(
            id_estado_cita__nombre_estado__iexact='No asistio'
        )

        data = {
            "ok": True,
            "citas_hoy": citas_validas.filter(fecha_cita=hoy).count(),
            "citas_proximos_7_dias": citas_validas.filter(fecha_cita__gte=hoy, fecha_cita__lte=fin_7_dias).count(),
            "pacientes_con_deuda": citas_pasadas_sin_pago.values('id_paciente').distinct().count(),
            "ingresos_semanales": to_float(ingresos_semanales),
            "ingresos_mes": to_float(ingresos_mes),
            "pagos_mes": pagos_mes_qs.count(),
            "ultimo_pago": ultimo_pago,
            "tasa_cancelaciones": tasa_cancelaciones,
            "canceladas_mes": canceladas_mes,
            "total_citas_mes": total_citas_mes,
            "correos_pendientes": 0,
            "whatsapp_pendientes": 0,
            "total_recordatorios_pendientes": 0,
            "recordatorios_pendientes": [],
            "pagos_recientes": [],
            "citas_proximas": [],
            "pacientes_pendientes_pago": [],
            "citas_estado_mes": [],
            "ultima_actualizacion_servidor": ahora_gt.strftime('%H:%M:%S'),
        }

        for p in pagos_mes_qs.order_by('-fecha_pago', '-id_pago')[:8]:
            data["pagos_recientes"].append({
                "id_pago": p.id_pago,
                "paciente": nombre_paciente(p.id_paciente),
                "monto": to_float(p.monto),
                "fecha_pago": p.fecha_pago.strftime('%Y-%m-%d %H:%M') if p.fecha_pago else '',
                "tipo_pago": p.id_tipo_pago.nombre_tipo_pago if p.id_tipo_pago else 'Sin tipo'
            })

        for c in citas_validas.filter(fecha_cita__gte=hoy, fecha_cita__lte=fin_7_dias).order_by('fecha_cita', 'hora_inicio')[:8]:
            data["citas_proximas"].append({
                "id_cita": c.id_cita,
                "paciente": nombre_paciente(c.id_paciente),
                "doctor": nombre_doctor(c.id_doctor),
                "fecha_cita": str(c.fecha_cita) if c.fecha_cita else '',
                "hora_inicio": str(c.hora_inicio)[:5] if c.hora_inicio else '',
                "estado": c.id_estado_cita.nombre_estado if c.id_estado_cita else 'Sin estado'
            })

        for c in citas_pasadas_sin_pago.order_by('-fecha_cita', '-hora_inicio')[:8]:
            data["pacientes_pendientes_pago"].append({
                "id_cita": c.id_cita,
                "paciente": nombre_paciente(c.id_paciente),
                "fecha_cita": str(c.fecha_cita) if c.fecha_cita else '',
                "hora_inicio": str(c.hora_inicio)[:5] if c.hora_inicio else '',
                "estado": c.id_estado_cita.nombre_estado if c.id_estado_cita else 'Sin estado'
            })

        estados_mes = citas_base.filter(
            fecha_cita__isnull=False,
            fecha_cita__year=hoy.year,
            fecha_cita__month=hoy.month
        ).values('id_estado_cita__nombre_estado').annotate(total=Count('id_cita')).order_by('-total')

        for item in estados_mes:
            data["citas_estado_mes"].append({
                "estado": item.get('id_estado_cita__nombre_estado') or 'Sin estado',
                "total": int(item.get('total') or 0)
            })

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM recordatorios
                    WHERE canal = %s AND estado_envio = %s
                    AND fecha_programada >= CURRENT_DATE
                """, ['correo', 'pendiente'])
                data["correos_pendientes"] = int(cursor.fetchone()[0] or 0)

                cursor.execute("""
                    SELECT COUNT(*) FROM recordatorios
                    WHERE canal = %s AND estado_envio = %s
                    AND fecha_programada >= CURRENT_DATE
                """, ['whatsapp', 'pendiente'])
                data["whatsapp_pendientes"] = int(cursor.fetchone()[0] or 0)

                cursor.execute("""
                    SELECT id_recordatorio, canal, tipo_recordatorio, destinatario, mensaje, fecha_programada, estado_envio
                    FROM recordatorios
                    WHERE estado_envio = %s
                    AND fecha_programada >= CURRENT_DATE
                    ORDER BY fecha_programada ASC
                    LIMIT 8
                """, ['pendiente'])
                filas = cursor.fetchall()

            data["total_recordatorios_pendientes"] = data["correos_pendientes"] + data["whatsapp_pendientes"]

            for fila in filas:
                data["recordatorios_pendientes"].append({
                    "id_recordatorio": fila[0],
                    "canal": fila[1],
                    "tipo_recordatorio": fila[2],
                    "destinatario": fila[3],
                    "mensaje": fila[4],
                    "fecha_programada": str(fila[5]) if fila[5] else '',
                    "estado_envio": fila[6],
                })
        except Exception:
            try:
                connection.rollback()
            except Exception:
                pass
            logger.exception('Error consultando recordatorios del dashboard')

        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})

    except Exception:
        logger.exception('Error generando el dashboard')
        return JsonResponse(
            {'ok': False, 'error': 'Error interno'},
            status=500,
            json_dumps_params={'ensure_ascii': False},
        )
