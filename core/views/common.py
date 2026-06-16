"""Imports, decoradores y helpers compartidos por las vistas."""

from functools import wraps
import json
import logging
import re
from datetime import date, datetime, timedelta, time
from urllib.parse import quote
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.middleware.csrf import get_token
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from django.core.mail import send_mail
from django.db import connection
from ..models import (
    Auditoria,
    Pacientes,
    Citas,
    Pagos,
    Doctores,
    EstadosCita,
    MotivosConsulta,
    Usuarios,
    Roles,
    TiposPago,
    NotasClinicas,
    Especialidades,
    ConfiguracionClinica
)

__all__ = [
    'Q',
    'escape',
    '_aplicar_paginacion',
    'Auditoria',
    'BLOQUEO_LOGIN_SEGUNDOS',
    'Citas',
    'Cm',
    'ConfiguracionClinica',
    'Count',
    'Doctores',
    'Document',
    'Especialidades',
    'EstadosCita',
    'HttpResponse',
    'JsonResponse',
    'MAX_INTENTOS_LOGIN',
    'MotivosConsulta',
    'NotasClinicas',
    'OxmlElement',
    'Pacientes',
    'Pagos',
    'Pt',
    'RGBColor',
    'Roles',
    'Sum',
    'TiposPago',
    'Usuarios',
    'WD_ALIGN_PARAGRAPH',
    '_DUMMY_PASSWORD_HASH',
    '_citas_recordatorio_qs',
    '_client_ip',
    '_doctor_de_sesion',
    '_es_doctor',
    '_hay_choque_citas',
    '_hora_como_time',
    '_mensaje_cita_recordatorio',
    '_mensaje_cita_recordatorio_doctor',
    '_nombre_paciente_cita',
    '_rango_recordatorios_dashboard',
    'cache',
    'check_password',
    'connection',
    'date',
    'datetime',
    'ensure_csrf_cookie',
    'get_object_or_404',
    'get_token',
    'json',
    'limpiar_numero_whatsapp',
    'logger',
    'logging',
    'make_password',
    'qn',
    'quote',
    're',
    'redirect',
    'registrar_auditoria',
    'render',
    'require_POST',
    'rol_requerido',
    'send_mail',
    'sistema_login_required',
    'time',
    'timedelta',
    'timezone',
    'wraps',
]


logger = logging.getLogger(__name__)


MAX_INTENTOS_LOGIN = 5


BLOQUEO_LOGIN_SEGUNDOS = 15 * 60


_DUMMY_PASSWORD_HASH = make_password('timing-dummy-password')


def _aplicar_paginacion(request, data_list):
    """
    Paginación opcional y compatible hacia atrás. Si la petición trae ?page,
    devuelve un dict {results, count, page, page_size, num_pages}; si no, devuelve
    None para que la vista responda la lista completa como antes.
    """
    if not request.GET.get('page'):
        return None
    try:
        page = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', 20))
    except (TypeError, ValueError):
        page_size = 20
    page_size = max(1, min(page_size, 200))
    paginator = Paginator(data_list, page_size)
    pagina = paginator.get_page(page)
    return {
        'results': list(pagina.object_list),
        'count': paginator.count,
        'page': pagina.number,
        'page_size': page_size,
        'num_pages': paginator.num_pages,
    }


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'desconocido'


def _es_doctor(request):
    """True si el rol de la sesión es Doctor."""
    return request.session.get('rol', '') == 'Doctor'


def _doctor_de_sesion(request):
    """Devuelve el registro Doctores del usuario en sesión, o None."""
    uid = request.session.get('usuario_id')
    if not uid:
        return None
    return Doctores.objects.filter(id_usuario_id=uid).first()


def _hay_choque_citas(doctor, fecha, hora_inicio, hora_fin, excluir_id=None):
    """
    True si el doctor ya tiene otra cita (no cancelada) que se solapa en
    fecha/hora con el rango indicado.
    """
    if not (doctor and fecha and hora_inicio and hora_fin):
        return False
    qs = Citas.objects.filter(
        id_doctor=doctor,
        fecha_cita=fecha,
        hora_inicio__lt=hora_fin,
        hora_fin__gt=hora_inicio,
    ).exclude(
        id_estado_cita__nombre_estado__iexact='Cancelada'
    ).exclude(
        id_estado_cita__nombre_estado__iexact='Cancelado'
    )
    if excluir_id is not None:
        qs = qs.exclude(id_cita=excluir_id)
    return qs.exists()


def registrar_auditoria(id_usuario, tabla, id_registro, accion, descripcion=''):
    """
    Registra una acción en la tabla de auditoría. Nunca debe romper la
    operación principal: si algo falla, solo se loggea.
    """
    try:
        Auditoria.objects.create(
            id_usuario_id=id_usuario or None,
            tabla_afectada=tabla,
            id_registro_afectado=id_registro,
            accion=accion,
            descripcion=descripcion,
            fecha_evento=timezone.now(),
        )
    except Exception:
        logger.exception('No se pudo registrar la auditoría (%s/%s)', tabla, accion)


def sistema_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def rol_requerido(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            es_api = request.path.startswith('/api/')

            if not request.session.get('usuario_id'):
                if es_api:
                    return JsonResponse({'ok': False, 'error': 'No autenticado'}, status=401)
                return redirect('/login/')

            rol = request.session.get('rol', '')

            if rol not in roles_permitidos:
                # No cerramos la sesión: el usuario sigue autenticado, solo no
                # tiene permiso para este módulo.
                if es_api:
                    return JsonResponse({'ok': False, 'error': 'No autorizado'}, status=403)
                return render(request, 'core/acceso_denegado.html', status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _hora_como_time(valor):
    if isinstance(valor, time):
        return valor

    if isinstance(valor, timedelta):
        segundos = int(valor.total_seconds())
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        segundos = segundos % 60
        return time(horas, minutos, segundos)

    if isinstance(valor, str):
        partes = valor.split(':')
        horas = int(partes[0]) if len(partes) > 0 and partes[0] else 8
        minutos = int(partes[1]) if len(partes) > 1 and partes[1] else 0
        segundos = int(partes[2]) if len(partes) > 2 and partes[2] else 0
        return time(horas, minutos, segundos)

    return time(8, 0, 0)


def _rango_recordatorios_dashboard():
    # No usamos timezone.localdate() porque en producción puede fallar si Django maneja datetime naive.
    # Para recordatorios manuales basta usar fecha local de Guatemala.
    try:
        from zoneinfo import ZoneInfo
        hoy = datetime.now(ZoneInfo('America/Guatemala')).date()
    except Exception:
        hoy = date.today()
    manana = hoy + timedelta(days=1)
    return hoy, manana


def _nombre_paciente_cita(cita):
    if not cita or not cita.id_paciente:
        return 'Paciente'
    return f"{cita.id_paciente.nombres or ''} {cita.id_paciente.apellidos or ''}".strip()


def _mensaje_cita_recordatorio(cita):
    hora_inicio = _hora_como_time(cita.hora_inicio)
    nombre = _nombre_paciente_cita(cita)
    modalidad = cita.modalidad or 'Presencial'
    motivo = cita.razon_consulta_detalle or 'Consulta médica'
    mensaje = (
        f"Hola {nombre}, le recordamos su cita médica programada para el "
        f"{cita.fecha_cita} a las {hora_inicio.strftime('%H:%M')}. "
        f"Modalidad: {modalidad}. Motivo: {motivo}. Clínica Nubnest."
    )
    if modalidad.lower() == 'virtual':
        link = f"https://meet.jit.si/ClinicaDS-{cita.id_cita}"
        mensaje += f" Enlace de su cita virtual: {link}"
    return mensaje


def _mensaje_cita_recordatorio_doctor(cita):
    hora_inicio = _hora_como_time(cita.hora_inicio)
    nombre_paciente = _nombre_paciente_cita(cita)
    modalidad = cita.modalidad or 'Presencial'
    motivo = cita.razon_consulta_detalle or 'Consulta médica'
    mensaje = (
        f"Recordatorio de cita: paciente {nombre_paciente} el {cita.fecha_cita} "
        f"a las {hora_inicio.strftime('%H:%M')}. "
        f"Modalidad: {modalidad}. Motivo: {motivo}. Clínica Nubnest."
    )
    if modalidad.lower() == 'virtual':
        link = f"https://meet.jit.si/ClinicaDS-{cita.id_cita}"
        mensaje += f" Enlace de la cita virtual: {link}"
    return mensaje


def _citas_recordatorio_qs():
    hoy, manana = _rango_recordatorios_dashboard()
    return Citas.objects.select_related(
        'id_paciente',
        'id_estado_cita',
        'id_doctor__id_usuario'
    ).filter(
        fecha_cita__gte=hoy,
        fecha_cita__lte=manana
    ).exclude(
        id_estado_cita__nombre_estado__iexact='Cancelada'
    ).exclude(
        id_estado_cita__nombre_estado__iexact='Cancelado'
    ).order_by('fecha_cita', 'hora_inicio')


def limpiar_numero_whatsapp(numero):
    numero = str(numero or '')
    numero = re.sub(r'\D', '', numero)
    if len(numero) == 8:
        numero = '502' + numero
    return numero
