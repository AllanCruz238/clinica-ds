from functools import wraps
import json
import re
from datetime import date, datetime, timedelta, time
from urllib.parse import quote
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from django.core.mail import send_mail
from django.db import connection

from .models import (
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
            if not request.session.get('usuario_id'):
                return redirect('/login/')

            rol = request.session.get('rol', '')

            if rol not in roles_permitidos:
                request.session.flush()
                return redirect('/login/?sin_acceso=1')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def login_page(request):
    if request.session.get('usuario_id'):
        return redirect('/dashboard/')
    return render(request, 'core/login.html')


@csrf_exempt
def login_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        username = body.get('username', '').strip()
        password = body.get('password', '').strip()

        usuario = Usuarios.objects.select_related('id_rol').filter(
            username=username,
            activo=1
        ).first()

        if not usuario:
            return JsonResponse({'ok': False, 'error': 'Usuario no encontrado'}, status=401)

        if not check_password(password, usuario.password_hash):
            return JsonResponse({'ok': False, 'error': 'Contraseña incorrecta'}, status=401)

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

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


def logout_view(request):
    request.session.flush()
    return redirect('/login/')


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
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
def pacientes_page(request):
    return render(request, 'core/pacientes.html')


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def pacientes_json(request):
    data = list(
        Pacientes.objects.values(
            'id_paciente',
            'nombres',
            'apellidos',
            'fecha_nacimiento',
            'sexo',
            'dpi_pasaporte',
            'direccion',
            'telefono',
            'correo',
            'ocupacion',
            'contacto_emergencia_nombre',
            'contacto_emergencia_telefono',
            'activo'
        )
    )

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def crear_paciente_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        nuevo_paciente = Pacientes.objects.create(
            nombres=body.get('nombres', ''),
            apellidos=body.get('apellidos', ''),
            fecha_nacimiento=body.get('fecha_nacimiento') or None,
            sexo=body.get('sexo', ''),
            dpi_pasaporte=body.get('dpi_pasaporte', ''),
            direccion=body.get('direccion', ''),
            telefono=body.get('telefono', ''),
            correo=body.get('correo', ''),
            ocupacion=body.get('ocupacion', ''),
            contacto_emergencia_nombre=body.get('contacto_emergencia_nombre', ''),
            contacto_emergencia_telefono=body.get('contacto_emergencia_telefono', ''),
            activo=1
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Paciente creado correctamente',
            'id_paciente': nuevo_paciente.id_paciente
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def actualizar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=id_paciente)

        paciente.nombres = body.get('nombres', '')
        paciente.apellidos = body.get('apellidos', '')
        paciente.fecha_nacimiento = body.get('fecha_nacimiento') or None
        paciente.sexo = body.get('sexo', '')
        paciente.dpi_pasaporte = body.get('dpi_pasaporte', '')
        paciente.direccion = body.get('direccion', '')
        paciente.telefono = body.get('telefono', '')
        paciente.correo = body.get('correo', '')
        paciente.ocupacion = body.get('ocupacion', '')
        paciente.contacto_emergencia_nombre = body.get('contacto_emergencia_nombre', '')
        paciente.contacto_emergencia_telefono = body.get('contacto_emergencia_telefono', '')

        paciente.save()

        return JsonResponse({'ok': True, 'mensaje': 'Paciente actualizado'}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def desactivar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        paciente = Pacientes.objects.get(id_paciente=id_paciente)
        paciente.activo = 0
        paciente.save()

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)



@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def activar_paciente_json(request, id_paciente):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        paciente = Pacientes.objects.get(id_paciente=id_paciente)
        paciente.activo = 1
        paciente.save()

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
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
                "id_motivo_consulta": c.id_motivo_consulta.id_motivo_consulta if c.id_motivo_consulta else ''
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


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def crear_cita_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        doctor = Doctores.objects.get(id_doctor=body['id_doctor'])
        estado = EstadosCita.objects.get(id_estado_cita=body['id_estado_cita'])
        motivo = MotivosConsulta.objects.get(id_motivo_consulta=body['id_motivo_consulta'])
        creado_por = Usuarios.objects.get(id_usuario=request.session.get('usuario_id'))

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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita creada correctamente',
            'id_cita': nueva_cita.id_cita
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def editar_cita_json(request, id_cita):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        cita = Citas.objects.get(id_cita=id_cita)
        cita.id_paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        cita.id_doctor = Doctores.objects.get(id_doctor=body['id_doctor'])
        cita.id_estado_cita = EstadosCita.objects.get(id_estado_cita=body['id_estado_cita'])
        cita.id_motivo_consulta = MotivosConsulta.objects.get(id_motivo_consulta=body['id_motivo_consulta'])
        cita.fecha_cita = body['fecha_cita']
        cita.hora_inicio = body['hora_inicio']
        cita.hora_fin = body['hora_fin']
        cita.modalidad = body.get('modalidad', '')
        cita.razon_consulta_detalle = body.get('razon_consulta_detalle', '')
        cita.observaciones = body.get('observaciones', '')
        cita.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita actualizada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


actualizar_cita_json = editar_cita_json


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def cancelar_cita_json(request, id_cita):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        cita = Citas.objects.get(id_cita=id_cita)
        estado_cancelada = EstadosCita.objects.get(nombre_estado__iexact='Cancelada')
        cita.id_estado_cita = estado_cancelada
        cita.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Cita cancelada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Recepción'])
def pagos_page(request):
    return render(request, 'core/pagos.html')


@rol_requerido(['Administrador', 'Recepción'])
def pagos_json(request):
    pagos = Pagos.objects.select_related(
        'id_paciente',
        'id_cita',
        'id_tipo_pago'
    ).order_by('-id_pago')

    data = []

    for p in pagos:
        data.append({
            'id_pago': p.id_pago,
            'paciente': f"{p.id_paciente.nombres} {p.id_paciente.apellidos}" if p.id_paciente else '',
            'id_paciente': p.id_paciente.id_paciente if p.id_paciente else None,
            'id_cita': p.id_cita.id_cita if p.id_cita else None,
            'tipo_pago': p.id_tipo_pago.nombre_tipo_pago if p.id_tipo_pago else '',
            'id_tipo_pago': p.id_tipo_pago.id_tipo_pago if p.id_tipo_pago else None,
            'monto': float(p.monto) if p.monto else 0,
            'fecha_pago': p.fecha_pago.strftime('%Y-%m-%d %H:%M') if p.fecha_pago else '',
            'referencia_pago': p.referencia_pago or '',
            'observaciones': p.observaciones or ''
        })

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción'])
def pagos_catalogos_json(request):
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
            'texto': f"Cita {c.id_cita} - {paciente} - {c.fecha_cita}"
        })

    tipos_pago = list(
        TiposPago.objects.filter(activo=1).values(
            'id_tipo_pago',
            'nombre_tipo_pago'
        )
    )

    return JsonResponse({
        'pacientes': pacientes,
        'citas': citas,
        'tipos_pago': tipos_pago
    }, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@rol_requerido(['Administrador', 'Recepción'])
def crear_pago_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        paciente = Pacientes.objects.get(id_paciente=body['id_paciente'])
        tipo_pago = TiposPago.objects.get(id_tipo_pago=body['id_tipo_pago'])

        cita = None
        if body.get('id_cita'):
            cita = Citas.objects.get(id_cita=body['id_cita'])

        nuevo_pago = Pagos.objects.create(
            id_paciente=paciente,
            id_cita=cita,
            id_tipo_pago=tipo_pago,
            monto=body.get('monto', 0),
            fecha_pago=timezone.now(),
            referencia_pago=body.get('referencia_pago', ''),
            observaciones=body.get('observaciones', '')
        )

        return JsonResponse({
            'ok': True,
            'mensaje': 'Pago registrado correctamente',
            'id_pago': nuevo_pago.id_pago
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador', 'Doctor'])
def notas_page(request):
    return render(request, 'core/notas.html')


@rol_requerido(['Administrador', 'Doctor'])
def notas_json(request):
    notas = NotasClinicas.objects.select_related(
        'id_paciente',
        'id_cita',
        'id_doctor__id_usuario'
    ).order_by('-id_nota_clinica')

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


@csrf_exempt
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Nota clínica guardada correctamente',
            'id_nota_clinica': nueva_nota.id_nota_clinica
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
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
        Especialidades.objects.filter(activo=1).values(
            'id_especialidad',
            'nombre_especialidad'
        )
    )

    return JsonResponse({
        'usuarios': usuarios,
        'especialidades': especialidades
    }, json_dumps_params={'ensure_ascii': False})


@csrf_exempt
@rol_requerido(['Administrador'])
def crear_doctor_json(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        usuario = Usuarios.objects.get(id_usuario=body['id_usuario'])
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Doctor creado correctamente',
            'id_doctor': nuevo_doctor.id_doctor
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador'])
def actualizar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        body = json.loads(request.body)

        doctor = Doctores.objects.select_related('id_usuario', 'id_especialidad').get(id_doctor=id_doctor)
        usuario = Usuarios.objects.get(id_usuario=body['id_usuario'])
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Doctor actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

@csrf_exempt
@rol_requerido(['Administrador'])
def desactivar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        doctor = Doctores.objects.get(id_doctor=id_doctor)
        doctor.activo = 0
        doctor.save()

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador'])
def activar_doctor_json(request, id_doctor):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        doctor = Doctores.objects.get(id_doctor=id_doctor)
        doctor.activo = 1
        doctor.save()

        return JsonResponse({'ok': True}, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
def usuarios_page(request):
    return render(request, 'core/usuarios.html')


@rol_requerido(['Administrador'])
def usuarios_json(request):
    usuarios = Usuarios.objects.select_related('id_rol').order_by('-id_usuario')

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


@csrf_exempt
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario creado correctamente',
            'id_usuario': nuevo_usuario.id_usuario
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario actualizado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario desactivado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@csrf_exempt
@rol_requerido(['Administrador'])
def activar_usuario_json(request, id_usuario):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido'}, status=405)

    try:
        usuario = Usuarios.objects.get(id_usuario=id_usuario)
        usuario.activo = 1
        usuario.save()

        return JsonResponse({
            'ok': True,
            'mensaje': 'Usuario activado correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@rol_requerido(['Administrador'])
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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


@rol_requerido(['Administrador'])
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


@csrf_exempt
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

        return JsonResponse({
            'ok': True,
            'mensaje': 'Configuración actualizada correctamente'
        }, json_dumps_params={'ensure_ascii': False})

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)




#@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
#def reportes_page(request):
#    return render(request, 'core/reportes.html')



@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def _datos_reporte_general():
    def fetchone_val(sql, params=None, default=0):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                row = cursor.fetchone()
            if not row:
                return default
            return row[0] if row[0] is not None else default
        except Exception as e:
            print("ERROR REPORTE fetchone:", e, sql)
            return default

    def fetchall(sql, params=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                return cursor.fetchall()
        except Exception as e:
            print("ERROR REPORTE fetchall:", e, sql)
            return []

    hoy = timezone.localdate()
    ahora = timezone.now()

    total_pacientes = int(fetchone_val("SELECT COUNT(*) FROM pacientes WHERE activo = 1"))
    total_pacientes_general = int(fetchone_val("SELECT COUNT(*) FROM pacientes"))
    total_usuarios = int(fetchone_val("SELECT COUNT(*) FROM usuarios"))
    usuarios_activos = int(fetchone_val("SELECT COUNT(*) FROM usuarios WHERE activo = 1"))
    total_doctores = int(fetchone_val("SELECT COUNT(*) FROM doctores"))
    doctores_activos = int(fetchone_val("SELECT COUNT(*) FROM doctores WHERE activo = 1"))
    total_citas = int(fetchone_val("SELECT COUNT(*) FROM citas"))
    total_pagos = int(fetchone_val("SELECT COUNT(*) FROM pagos"))

    citas_hoy = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita = CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    citas_proximas_total = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita >= CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    ingresos_totales = float(fetchone_val("SELECT COALESCE(SUM(monto),0) FROM pagos", default=0) or 0)
    pagos_del_mes = float(fetchone_val("""
        SELECT COALESCE(SUM(monto),0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND MONTH(fecha_pago) = MONTH(CURDATE())
          AND YEAR(fecha_pago) = YEAR(CURDATE())
    """, default=0) or 0)
    ingresos_semanales = float(fetchone_val("""
        SELECT COALESCE(SUM(monto),0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND fecha_pago >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, default=0) or 0)

    promedio_pago = round((ingresos_totales / total_pagos), 2) if total_pagos else 0
    citas_futuras_pendientes_pago = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN pagos p ON c.id_cita = p.id_cita
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita >= CURDATE()
          AND p.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))
    ingresos_potenciales = round(promedio_pago * citas_futuras_pendientes_pago, 2)

    canceladas = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        INNER JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE LOWER(e.nombre_estado) IN ('cancelada', 'cancelado')
    """))
    tasa_cancelaciones = round((canceladas / total_citas) * 100, 2) if total_citas else 0

    citas_por_estado = []
    for estado, total in fetchall("""
        SELECT COALESCE(e.nombre_estado, 'Sin estado') AS estado, COUNT(c.id_cita) AS total
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        GROUP BY estado
        ORDER BY total DESC
    """):
        citas_por_estado.append({'estado': estado, 'total': int(total or 0)})

    pacientes_frecuentes = []
    for id_paciente, nombres, apellidos, total in fetchall("""
        SELECT p.id_paciente, p.nombres, p.apellidos, COUNT(c.id_cita) AS total
        FROM citas c
        INNER JOIN pacientes p ON c.id_paciente = p.id_paciente
        GROUP BY p.id_paciente, p.nombres, p.apellidos
        ORDER BY total DESC
        LIMIT 10
    """):
        pacientes_frecuentes.append({
            'id_paciente': id_paciente,
            'paciente': f"{nombres or ''} {apellidos or ''}".strip(),
            'total_citas': int(total or 0)
        })

    cumpleanios_mes = []
    for id_paciente, nombres, apellidos, fecha_nacimiento in fetchall("""
        SELECT id_paciente, nombres, apellidos, fecha_nacimiento
        FROM pacientes
        WHERE activo = 1
          AND fecha_nacimiento IS NOT NULL
          AND MONTH(fecha_nacimiento) = MONTH(CURDATE())
        ORDER BY DAY(fecha_nacimiento), nombres
    """):
        cumpleanios_mes.append({
            'id_paciente': id_paciente,
            'paciente': f"{nombres or ''} {apellidos or ''}".strip(),
            'fecha_nacimiento': str(fecha_nacimiento) if fecha_nacimiento else ''
        })

    ingresos_por_tipo = []
    for tipo, cantidad, total in fetchall("""
        SELECT COALESCE(t.nombre_tipo_pago, 'Sin tipo') AS tipo, COUNT(p.id_pago) AS cantidad, COALESCE(SUM(p.monto),0) AS total
        FROM pagos p
        LEFT JOIN tipos_pago t ON p.id_tipo_pago = t.id_tipo_pago
        GROUP BY tipo
        ORDER BY total DESC
    """):
        ingresos_por_tipo.append({
            'tipo_pago': tipo,
            'cantidad': int(cantidad or 0),
            'total': float(total or 0)
        })

    citas_proximas = []
    for row in fetchall("""
        SELECT
            c.id_cita,
            p.nombres,
            p.apellidos,
            ud.nombres,
            ud.apellidos,
            c.fecha_cita,
            c.hora_inicio,
            c.hora_fin,
            COALESCE(e.nombre_estado, 'Sin estado') AS estado,
            COALESCE(c.modalidad, '') AS modalidad,
            COALESCE(m.nombre_motivo, '') AS motivo,
            COALESCE(c.razon_consulta_detalle, '') AS detalle
        FROM citas c
        LEFT JOIN pacientes p ON c.id_paciente = p.id_paciente
        LEFT JOIN doctores d ON c.id_doctor = d.id_doctor
        LEFT JOIN usuarios ud ON d.id_usuario = ud.id_usuario
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        LEFT JOIN motivos_consulta m ON c.id_motivo_consulta = m.id_motivo_consulta
        WHERE c.fecha_cita >= CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita ASC, c.hora_inicio ASC
        LIMIT 30
    """):
        (id_cita, pn, pa, dn, da, fecha_cita, hora_inicio, hora_fin, estado, modalidad, motivo, detalle) = row
        citas_proximas.append({
            'id_cita': id_cita,
            'paciente': f"{pn or ''} {pa or ''}".strip(),
            'doctor': f"{dn or ''} {da or ''}".strip(),
            'fecha_cita': str(fecha_cita) if fecha_cita else '',
            'hora_inicio': str(hora_inicio)[:5] if hora_inicio else '',
            'hora_fin': str(hora_fin)[:5] if hora_fin else '',
            'estado': estado,
            'modalidad': modalidad,
            'motivo': motivo,
            'detalle': detalle
        })

    sesiones_pendientes = []
    for row in fetchall("""
        SELECT
            c.id_cita,
            p.nombres,
            p.apellidos,
            ud.nombres,
            ud.apellidos,
            c.fecha_cita,
            c.hora_inicio,
            COALESCE(e.nombre_estado, 'Sin estado') AS estado
        FROM citas c
        LEFT JOIN pagos pg ON c.id_cita = pg.id_cita
        LEFT JOIN pacientes p ON c.id_paciente = p.id_paciente
        LEFT JOIN doctores d ON c.id_doctor = d.id_doctor
        LEFT JOIN usuarios ud ON d.id_usuario = ud.id_usuario
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE pg.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita DESC, c.hora_inicio DESC
        LIMIT 30
    """):
        (id_cita, pn, pa, dn, da, fecha_cita, hora_inicio, estado) = row
        sesiones_pendientes.append({
            'id_cita': id_cita,
            'paciente': f"{pn or ''} {pa or ''}".strip(),
            'doctor': f"{dn or ''} {da or ''}".strip(),
            'fecha_cita': str(fecha_cita) if fecha_cita else '',
            'hora_inicio': str(hora_inicio)[:5] if hora_inicio else '',
            'estado': estado
        })

    usuarios_resumen = []
    for row in fetchall("""
        SELECT u.id_usuario, u.username, u.nombres, u.apellidos, COALESCE(r.nombre_rol, '') AS rol, u.correo, u.activo
        FROM usuarios u
        LEFT JOIN roles r ON u.id_rol = r.id_rol
        ORDER BY u.id_usuario DESC
        LIMIT 50
    """):
        id_usuario, username, nombres, apellidos, rol, correo, activo = row
        usuarios_resumen.append({
            'id_usuario': id_usuario,
            'usuario': username or '',
            'nombre': f"{nombres or ''} {apellidos or ''}".strip(),
            'rol': rol,
            'correo': correo or '',
            'activo': int(activo or 0)
        })

    doctores_resumen = []
    for row in fetchall("""
        SELECT d.id_doctor, u.nombres, u.apellidos, COALESCE(e.nombre_especialidad, '') AS especialidad,
               u.correo, u.telefono, d.numero_colegiado, d.activo
        FROM doctores d
        LEFT JOIN usuarios u ON d.id_usuario = u.id_usuario
        LEFT JOIN especialidades e ON d.id_especialidad = e.id_especialidad
        ORDER BY d.id_doctor DESC
        LIMIT 50
    """):
        id_doctor, nombres, apellidos, especialidad, correo, telefono, colegiado, activo = row
        doctores_resumen.append({
            'id_doctor': id_doctor,
            'doctor': f"{nombres or ''} {apellidos or ''}".strip(),
            'especialidad': especialidad,
            'correo': correo or '',
            'telefono': telefono or '',
            'colegiado': colegiado or '',
            'activo': int(activo or 0)
        })

    return {
        'fecha_generacion': ahora.strftime('%Y-%m-%d %H:%M:%S'),
        'total_pacientes': total_pacientes,
        'total_pacientes_general': total_pacientes_general,
        'total_usuarios': total_usuarios,
        'usuarios_activos': usuarios_activos,
        'total_doctores': total_doctores,
        'doctores_activos': doctores_activos,
        'total_citas': total_citas,
        'citas_hoy': citas_hoy,
        'citas_proximas_total': citas_proximas_total,
        'total_pagos': total_pagos,
        'ingresos_totales': ingresos_totales,
        'pagos_del_mes': pagos_del_mes,
        'ingresos_semanales': ingresos_semanales,
        'ingresos_potenciales': ingresos_potenciales,
        'citas_futuras_pendientes_pago': citas_futuras_pendientes_pago,
        'promedio_pago': promedio_pago,
        'tasa_cancelaciones': tasa_cancelaciones,
        'citas_por_estado': citas_por_estado,
        'pacientes_frecuentes': pacientes_frecuentes,
        'cumpleanios_mes': cumpleanios_mes,
        'ingresos_por_tipo': ingresos_por_tipo,
        'citas_proximas': citas_proximas,
        'sesiones_pendientes': sesiones_pendientes,
        'usuarios_resumen': usuarios_resumen,
        'doctores_resumen': doctores_resumen,
    }


# @rol_requerido(['Administrador', 'Recepción', 'Doctor'])
# def reportes_json(request):
#     try:
#         return JsonResponse(_datos_reporte_general(), json_dumps_params={'ensure_ascii': False})
#     except Exception as e:
#         print('ERROR GENERAL REPORTES:', e)
#         return JsonResponse({'ok': False, 'error': str(e)}, status=500, json_dumps_params={'ensure_ascii': False})


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def generar_word_reporte_general(request):
    data = _datos_reporte_general()

    def valor(v):
        if v is None or v == '':
            return 'No registrado'
        return str(v)

    def agregar_tabla(documento, encabezados, filas):
        tabla = documento.add_table(rows=1, cols=len(encabezados))
        tabla.style = "Table Grid"
        for i, encabezado in enumerate(encabezados):
            tabla.rows[0].cells[i].text = str(encabezado)
        for fila_data in filas:
            fila = tabla.add_row().cells
            for i, dato in enumerate(fila_data):
                fila[i].text = valor(dato)
        return tabla

    documento = Document()
    titulo = documento.add_heading("Reporte General del Sistema Clínico", level=1)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    documento.add_paragraph("Clínica DS")
    documento.add_paragraph(f"Fecha de generación: {data.get('fecha_generacion')}")
    documento.add_paragraph("")

    documento.add_heading("Resumen general", level=2)
    agregar_tabla(documento, ["Indicador", "Valor"], [
        ["Pacientes activos", data.get('total_pacientes')],
        ["Pacientes registrados", data.get('total_pacientes_general')],
        ["Usuarios totales", data.get('total_usuarios')],
        ["Usuarios activos", data.get('usuarios_activos')],
        ["Doctores totales", data.get('total_doctores')],
        ["Doctores activos", data.get('doctores_activos')],
        ["Total citas", data.get('total_citas')],
        ["Citas de hoy", data.get('citas_hoy')],
        ["Citas próximas", data.get('citas_proximas_total')],
        ["Total pagos", data.get('total_pagos')],
        ["Ingresos totales", f"Q{float(data.get('ingresos_totales', 0)):.2f}"],
        ["Ingresos del mes", f"Q{float(data.get('pagos_del_mes', 0)):.2f}"],
        ["Ingresos semanales", f"Q{float(data.get('ingresos_semanales', 0)):.2f}"],
        ["Ingresos potenciales", f"Q{float(data.get('ingresos_potenciales', 0)):.2f}"],
        ["Tasa de cancelaciones", f"{data.get('tasa_cancelaciones')}%"],
    ])

    secciones = [
        ("Citas por estado", ["Estado", "Total"], [[x.get('estado'), x.get('total')] for x in data.get('citas_por_estado', [])]),
        ("Ingresos por tipo de pago", ["Tipo", "Cantidad", "Total"], [[x.get('tipo_pago'), x.get('cantidad'), f"Q{float(x.get('total', 0)):.2f}"] for x in data.get('ingresos_por_tipo', [])]),
        ("Citas próximas", ["ID", "Paciente", "Doctor", "Fecha", "Inicio", "Fin", "Estado", "Modalidad", "Motivo"], [[x.get('id_cita'), x.get('paciente'), x.get('doctor'), x.get('fecha_cita'), x.get('hora_inicio'), x.get('hora_fin'), x.get('estado'), x.get('modalidad'), x.get('motivo')] for x in data.get('citas_proximas', [])]),
        ("Pacientes frecuentes", ["Paciente", "Total citas"], [[x.get('paciente'), x.get('total_citas')] for x in data.get('pacientes_frecuentes', [])]),
        ("Doctores", ["ID", "Doctor", "Especialidad", "Correo", "Teléfono", "Colegiado", "Activo"], [[x.get('id_doctor'), x.get('doctor'), x.get('especialidad'), x.get('correo'), x.get('telefono'), x.get('colegiado'), "Sí" if x.get('activo') else "No"] for x in data.get('doctores_resumen', [])]),
        ("Usuarios", ["ID", "Usuario", "Nombre", "Rol", "Correo", "Activo"], [[x.get('id_usuario'), x.get('usuario'), x.get('nombre'), x.get('rol'), x.get('correo'), "Sí" if x.get('activo') else "No"] for x in data.get('usuarios_resumen', [])]),
        ("Sesiones pendientes de pago", ["Cita", "Paciente", "Doctor", "Fecha", "Hora", "Estado"], [[x.get('id_cita'), x.get('paciente'), x.get('doctor'), x.get('fecha_cita'), x.get('hora_inicio'), x.get('estado')] for x in data.get('sesiones_pendientes', [])]),
    ]

    for titulo_seccion, encabezados, filas in secciones:
        documento.add_paragraph("")
        documento.add_heading(titulo_seccion, level=2)
        agregar_tabla(documento, encabezados, filas or [["Sin datos"] + [""] * (len(encabezados) - 1)])

    for parrafo in documento.paragraphs:
        for run in parrafo.runs:
            run.font.name = "Arial"
            run.font.size = Pt(11)

    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    for run in parrafo.runs:
                        run.font.name = "Arial"
                        run.font.size = Pt(9)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    response["Content-Disposition"] = 'attachment; filename="reporte_general_clinica.docx"'
    documento.save(response)
    return response


@rol_requerido(['Administrador', 'Recepción', 'Doctor'])
def generar_word_paciente(request, id_paciente):
    paciente = get_object_or_404(Pacientes, id_paciente=id_paciente)

    def valor(valor_original):
        if valor_original is None or valor_original == "":
            return "No registrado"
        return str(valor_original)

    def fecha(valor_fecha):
        if not valor_fecha:
            return "No registrado"
        try:
            return valor_fecha.strftime("%Y-%m-%d")
        except Exception:
            return str(valor_fecha)

    def fecha_hora(valor_fecha):
        if not valor_fecha:
            return "No registrado"
        try:
            return valor_fecha.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(valor_fecha)

    def hora(valor_hora):
        if not valor_hora:
            return "No registrado"
        try:
            return valor_hora.strftime("%H:%M")
        except Exception:
            return str(valor_hora)

    def aplicar_fuente(documento):
        for parrafo in documento.paragraphs:
            for run in parrafo.runs:
                run.font.name = "Arial"
                run.font.size = Pt(11)

        for tabla in documento.tables:
            for fila in tabla.rows:
                for celda in fila.cells:
                    for parrafo in celda.paragraphs:
                        for run in parrafo.runs:
                            run.font.name = "Arial"
                            run.font.size = Pt(9)

    def agregar_tabla_dos_columnas(documento, datos):
        tabla = documento.add_table(rows=0, cols=2)
        tabla.style = "Table Grid"

        for etiqueta, dato in datos:
            fila = tabla.add_row().cells
            fila[0].text = str(etiqueta)
            fila[1].text = valor(dato)

        return tabla

    def agregar_tabla_registros(documento, encabezados, registros):
        tabla = documento.add_table(rows=1, cols=len(encabezados))
        tabla.style = "Table Grid"

        for i, encabezado in enumerate(encabezados):
            tabla.rows[0].cells[i].text = str(encabezado)

        for registro in registros:
            fila = tabla.add_row().cells
            for i, dato in enumerate(registro):
                fila[i].text = valor(dato)

        return tabla

    documento = Document()

    titulo = documento.add_heading("Reporte Clínico del Paciente", level=1)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER

    documento.add_paragraph("Clínica Médica DS")
    documento.add_paragraph("Documento generado desde el sistema clínico.")
    documento.add_paragraph("")

    # =========================
    # DATOS DEL PACIENTE
    # =========================
    documento.add_heading("Datos del paciente", level=2)

    datos_paciente = [
        ("ID", paciente.id_paciente),
        ("Nombres", paciente.nombres),
        ("Apellidos", paciente.apellidos),
        ("Fecha de nacimiento", fecha(paciente.fecha_nacimiento)),
        ("Sexo", paciente.sexo),
        ("DPI / Pasaporte", paciente.dpi_pasaporte),
        ("Dirección", paciente.direccion),
        ("Teléfono", paciente.telefono),
        ("Correo", paciente.correo),
        ("Ocupación", paciente.ocupacion),
        ("Contacto de emergencia", paciente.contacto_emergencia_nombre),
        ("Teléfono de emergencia", paciente.contacto_emergencia_telefono),
        ("Activo", "Sí" if paciente.activo else "No"),
    ]

    agregar_tabla_dos_columnas(documento, datos_paciente)
    documento.add_paragraph("")

    # =========================
    # CITAS
    # =========================
    documento.add_heading("Historial de citas", level=2)

    citas = Citas.objects.select_related(
        "id_doctor__id_usuario",
        "id_estado_cita",
        "id_motivo_consulta"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_cita", "-hora_inicio", "-id_cita")

    if citas.exists():
        registros_citas = []

        for cita in citas:
            doctor = "No asignado"
            if cita.id_doctor and cita.id_doctor.id_usuario:
                doctor = f"{cita.id_doctor.id_usuario.nombres} {cita.id_doctor.id_usuario.apellidos}"

            estado = cita.id_estado_cita.nombre_estado if cita.id_estado_cita else "Sin estado"
            motivo = cita.id_motivo_consulta.nombre_motivo if cita.id_motivo_consulta else "Sin motivo"

            registros_citas.append([
                cita.id_cita,
                fecha(cita.fecha_cita),
                hora(cita.hora_inicio),
                hora(cita.hora_fin),
                doctor,
                estado,
                motivo,
                cita.modalidad,
                cita.razon_consulta_detalle,
                cita.observaciones,
            ])

        agregar_tabla_registros(
            documento,
            [
                "ID cita",
                "Fecha",
                "Inicio",
                "Fin",
                "Doctor",
                "Estado",
                "Motivo",
                "Modalidad",
                "Detalle",
                "Observaciones",
            ],
            registros_citas
        )
    else:
        documento.add_paragraph("No hay citas registradas para este paciente.")

    documento.add_paragraph("")

    # =========================
    # NOTAS CLÍNICAS
    # =========================
    documento.add_heading("Notas clínicas", level=2)

    notas = NotasClinicas.objects.select_related(
        "id_cita",
        "id_doctor__id_usuario"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_nota", "-id_nota_clinica")

    if notas.exists():
        for nota in notas:
            doctor = "No asignado"
            if nota.id_doctor and nota.id_doctor.id_usuario:
                doctor = f"{nota.id_doctor.id_usuario.nombres} {nota.id_doctor.id_usuario.apellidos}"

            documento.add_paragraph(f"Nota #{nota.id_nota_clinica}", style="List Bullet")
            agregar_tabla_dos_columnas(
                documento,
                [
                    ("Fecha", fecha_hora(nota.fecha_nota)),
                    ("Cita relacionada", nota.id_cita.id_cita if nota.id_cita else "No registrada"),
                    ("Doctor", doctor),
                    ("Título", nota.titulo),
                    ("Contenido", nota.contenido),
                    ("Recomendaciones", nota.recomendaciones),
                ]
            )
            documento.add_paragraph("")
    else:
        documento.add_paragraph("No hay notas clínicas registradas para este paciente.")

    documento.add_paragraph("")

    # =========================
    # PAGOS
    # =========================
    documento.add_heading("Pagos registrados", level=2)

    pagos = Pagos.objects.select_related(
        "id_cita",
        "id_tipo_pago"
    ).filter(
        id_paciente=paciente
    ).order_by("-fecha_pago", "-id_pago")

    if pagos.exists():
        registros_pagos = []

        for pago in pagos:
            tipo_pago = pago.id_tipo_pago.nombre_tipo_pago if pago.id_tipo_pago else "Sin tipo"

            registros_pagos.append([
                pago.id_pago,
                pago.id_cita.id_cita if pago.id_cita else "No registrada",
                tipo_pago,
                f"Q {pago.monto}",
                fecha_hora(pago.fecha_pago),
                pago.referencia_pago,
                pago.observaciones,
            ])

        agregar_tabla_registros(
            documento,
            [
                "ID pago",
                "ID cita",
                "Tipo de pago",
                "Monto",
                "Fecha de pago",
                "Referencia",
                "Observaciones",
            ],
            registros_pagos
        )
    else:
        documento.add_paragraph("No hay pagos registrados para este paciente.")

    aplicar_fuente(documento)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    nombre_archivo = f"reporte_paciente_{paciente.id_paciente}.docx"
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'

    documento.save(response)
    return response


def enviar_recordatorios_correo(request):
    enviados = 0
    errores = 0

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id_recordatorio,
                destinatario,
                mensaje
            FROM recordatorios
            WHERE canal = 'correo'
              AND estado_envio = 'pendiente'
              AND fecha_programada <= NOW()
        """)

        recordatorios = cursor.fetchall()

    for recordatorio in recordatorios:
        id_recordatorio = recordatorio[0]
        destinatario = recordatorio[1]
        mensaje = recordatorio[2]

        try:
            send_mail(
                subject="Recordatorio de cita médica",
                message=mensaje,
                from_email="clinica@clinica-ds.com",
                recipient_list=[destinatario],
                fail_silently=False,
            )

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE recordatorios
                    SET estado_envio = 'enviado'
                    WHERE id_recordatorio = %s
                """, [id_recordatorio])

            enviados += 1

        except Exception as e:
            errores += 1
            print("ERROR AL ENVIAR CORREO:", e)

    return HttpResponse(
        f"Recordatorios procesados. Enviados: {enviados}. Errores: {errores}."
    )



def limpiar_numero_whatsapp(numero):
    numero = str(numero)
    numero = re.sub(r'\D', '', numero)

    # Si es número de Guatemala de 8 dígitos, agregar código de país 502
    if len(numero) == 8:
        numero = "502" + numero

    return numero


@rol_requerido(['Administrador', 'Recepción'])
def listar_recordatorios_whatsapp(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                id_recordatorio,
                destinatario,
                mensaje,
                fecha_programada
            FROM recordatorios
            WHERE canal = 'whatsapp'
              AND estado_envio = 'pendiente'
              AND fecha_programada <= NOW()
            ORDER BY fecha_programada ASC
        """)

        recordatorios = cursor.fetchall()

    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Recordatorios WhatsApp</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                padding: 30px;
            }

            h1 {
                color: #111827;
            }

            .card {
                background: white;
                border-radius: 12px;
                padding: 18px;
                margin-bottom: 15px;
                box-shadow: 0 8px 20px rgba(0,0,0,0.08);
            }

            .numero {
                font-weight: bold;
                color: #111827;
                margin-bottom: 8px;
            }

            .fecha {
                color: #6b7280;
                font-size: 14px;
                margin-bottom: 10px;
            }

            .mensaje {
                background: #f9fafb;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 12px;
                white-space: pre-wrap;
            }

            .btn {
                display: inline-block;
                background: #16a34a;
                color: white;
                text-decoration: none;
                padding: 10px 14px;
                border-radius: 8px;
                font-weight: bold;
            }

            .empty {
                background: white;
                padding: 20px;
                border-radius: 12px;
                color: #374151;
            }
        </style>
    </head>
    <body>
        <h1>Recordatorios pendientes por WhatsApp</h1>
    """

    if not recordatorios:
        html += """
        <div class="empty">
            No hay recordatorios pendientes por WhatsApp.
        </div>
        """
    else:
        for recordatorio in recordatorios:
            id_recordatorio = recordatorio[0]
            destinatario = recordatorio[1]
            mensaje = recordatorio[2]
            fecha_programada = recordatorio[3]

            html += f"""
            <div class="card">
                <div class="numero">Número: {destinatario}</div>
                <div class="fecha">Fecha programada: {fecha_programada}</div>
                <div class="mensaje">{mensaje}</div>
                <a class="btn" target="_blank" href="/recordatorios/whatsapp/{id_recordatorio}/abrir/">
                    Abrir WhatsApp
                </a>
            </div>
            """

    html += """
    </body>
    </html>
    """

    return HttpResponse(html)


@rol_requerido(['Administrador', 'Recepción'])
def abrir_recordatorio_whatsapp(request, id_recordatorio):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                destinatario,
                mensaje
            FROM recordatorios
            WHERE id_recordatorio = %s
              AND canal = 'whatsapp'
        """, [id_recordatorio])

        recordatorio = cursor.fetchone()

    if not recordatorio:
        return HttpResponse("Recordatorio no encontrado", status=404)

    destinatario = recordatorio[0]
    mensaje = recordatorio[1]

    numero_limpio = limpiar_numero_whatsapp(destinatario)
    mensaje_codificado = quote(str(mensaje))

    url_whatsapp = f"https://wa.me/{numero_limpio}?text={mensaje_codificado}"

    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE recordatorios
            SET estado_envio = 'enviado'
            WHERE id_recordatorio = %s
        """, [id_recordatorio])

    return redirect(url_whatsapp)



@rol_requerido(['Administrador', 'Recepción'])
def generar_recordatorios_automaticos(request):
    creados = 0
    omitidos = 0
    errores = 0

    def convertir_hora(valor):
        if isinstance(valor, time):
            return valor

        if isinstance(valor, timedelta):
            segundos = int(valor.total_seconds())
            horas = segundos // 3600
            minutos = (segundos % 3600) // 60
            segundos = segundos % 60
            return time(horas, minutos, segundos)

        if isinstance(valor, str):
            partes = valor.split(":")
            horas = int(partes[0])
            minutos = int(partes[1]) if len(partes) > 1 else 0
            segundos = int(partes[2]) if len(partes) > 2 else 0
            return time(horas, minutos, segundos)

        return time(8, 0, 0)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.id_cita,
                c.id_paciente,
                c.fecha_cita,
                c.hora_inicio,
                c.modalidad,
                c.razon_consulta_detalle,
                p.nombres,
                p.apellidos,
                p.telefono,
                p.correo
            FROM citas c
            INNER JOIN pacientes p ON c.id_paciente = p.id_paciente
            WHERE c.fecha_cita >= CURDATE()
            ORDER BY c.fecha_cita ASC, c.hora_inicio ASC
        """)

        citas = cursor.fetchall()

    for cita in citas:
        try:
            id_cita = cita[0]
            id_paciente = cita[1]
            fecha_cita = cita[2]
            hora_inicio = convertir_hora(cita[3])
            modalidad = cita[4]
            razon = cita[5]
            nombres = cita[6]
            apellidos = cita[7]
            telefono = cita[8]
            correo = cita[9]

            fecha_hora_cita = datetime.combine(fecha_cita, hora_inicio)
            nombre_completo = f"{nombres} {apellidos}".strip()

            mensaje = (
                f"Hola {nombre_completo}, le recordamos su cita médica "
                f"programada para el {fecha_cita} a las {hora_inicio.strftime('%H:%M')}. "
                f"Modalidad: {modalidad if modalidad else 'No registrada'}. "
                f"Motivo: {razon if razon else 'Consulta médica'}. "
                f"Clínica DS."
            )

            recordatorios = [
                {
                    "canal": "correo",
                    "tipo": "1_dia_antes",
                    "destinatario": correo,
                    "fecha_programada": fecha_hora_cita - timedelta(days=1),
                },
                {
                    "canal": "correo",
                    "tipo": "3_horas_antes",
                    "destinatario": correo,
                    "fecha_programada": fecha_hora_cita - timedelta(hours=3),
                },
                {
                    "canal": "whatsapp",
                    "tipo": "1_dia_antes",
                    "destinatario": telefono,
                    "fecha_programada": fecha_hora_cita - timedelta(days=1),
                },
                {
                    "canal": "whatsapp",
                    "tipo": "3_horas_antes",
                    "destinatario": telefono,
                    "fecha_programada": fecha_hora_cita - timedelta(hours=3),
                },
            ]

            for r in recordatorios:
                if not r["destinatario"]:
                    omitidos += 1
                    continue

                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*)
                        FROM recordatorios
                        WHERE id_cita = %s
                          AND canal = %s
                          AND tipo_recordatorio = %s
                    """, [id_cita, r["canal"], r["tipo"]])

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
                        VALUES (%s, %s, %s, %s, %s, %s, 'pendiente')
                    """, [
                        id_cita,
                        r["canal"],
                        r["tipo"],
                        r["destinatario"],
                        mensaje,
                        r["fecha_programada"]
                    ])

                creados += 1

        except Exception as e:
            errores += 1
            print("ERROR GENERANDO RECORDATORIO:", e)

    return HttpResponse(
        f"Recordatorios generados. Creados: {creados}. Omitidos: {omitidos}. Errores: {errores}."
    )


def api_dashboard_recordatorios(request):
    def fetchone_val(sql, params=None, default=0):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                row = cursor.fetchone()
            if not row or row[0] is None:
                return default
            return row[0]
        except Exception as e:
            print("ERROR DASHBOARD fetchone:", e, sql)
            return default

    def fetchall(sql, params=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params or [])
                return cursor.fetchall()
        except Exception as e:
            print("ERROR DASHBOARD fetchall:", e, sql)
            return []

    data = {
        "citas_hoy": 0,
        "citas_proximos_7_dias": 0,
        "pacientes_con_deuda": 0,
        "ingresos_semanales": 0,
        "ingresos_mes": 0,
        "pagos_mes": 0,
        "ultimo_pago": 0,
        "tasa_cancelaciones": 0,
        "canceladas_mes": 0,
        "total_citas_mes": 0,
        "correos_pendientes": 0,
        "whatsapp_pendientes": 0,
        "total_recordatorios_pendientes": 0,
        "recordatorios_pendientes": [],
        "pagos_recientes": [],
        "citas_proximas": [],
        "pacientes_pendientes_pago": [],
        "citas_estado_mes": [],
        "ultima_actualizacion_servidor": datetime.now().strftime('%H:%M:%S')
    }

    data["citas_hoy"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita = CURDATE()
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    data["citas_proximos_7_dias"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    data["ingresos_semanales"] = float(fetchone_val("""
        SELECT COALESCE(SUM(monto), 0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND fecha_pago >= DATE_SUB(NOW(), INTERVAL 7 DAY)
    """, default=0) or 0)

    data["ingresos_mes"] = float(fetchone_val("""
        SELECT COALESCE(SUM(monto), 0)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND MONTH(fecha_pago) = MONTH(CURDATE())
          AND YEAR(fecha_pago) = YEAR(CURDATE())
    """, default=0) or 0)

    data["pagos_mes"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM pagos
        WHERE fecha_pago IS NOT NULL
          AND MONTH(fecha_pago) = MONTH(CURDATE())
          AND YEAR(fecha_pago) = YEAR(CURDATE())
    """))

    data["ultimo_pago"] = float(fetchone_val("""
        SELECT COALESCE(monto, 0)
        FROM pagos
        ORDER BY fecha_pago DESC, id_pago DESC
        LIMIT 1
    """, default=0) or 0)

    data["total_citas_mes"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas
        WHERE fecha_cita IS NOT NULL
          AND MONTH(fecha_cita) = MONTH(CURDATE())
          AND YEAR(fecha_cita) = YEAR(CURDATE())
    """))

    data["canceladas_mes"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM citas c
        INNER JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita IS NOT NULL
          AND MONTH(c.fecha_cita) = MONTH(CURDATE())
          AND YEAR(c.fecha_cita) = YEAR(CURDATE())
          AND LOWER(e.nombre_estado) IN ('cancelada', 'cancelado')
    """))

    data["tasa_cancelaciones"] = round((data["canceladas_mes"] / data["total_citas_mes"]) * 100, 2) if data["total_citas_mes"] else 0

    data["pacientes_con_deuda"] = int(fetchone_val("""
        SELECT COUNT(DISTINCT c.id_paciente)
        FROM citas c
        LEFT JOIN pagos p ON c.id_cita = p.id_cita
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita < CURDATE()
          AND p.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
    """))

    data["correos_pendientes"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM recordatorios
        WHERE canal = 'correo'
          AND estado_envio = 'pendiente'
    """))

    data["whatsapp_pendientes"] = int(fetchone_val("""
        SELECT COUNT(*)
        FROM recordatorios
        WHERE canal = 'whatsapp'
          AND estado_envio = 'pendiente'
    """))

    data["total_recordatorios_pendientes"] = data["correos_pendientes"] + data["whatsapp_pendientes"]

    for fila in fetchall("""
        SELECT id_recordatorio, canal, tipo_recordatorio, destinatario, mensaje, fecha_programada, estado_envio
        FROM recordatorios
        WHERE estado_envio = 'pendiente'
        ORDER BY fecha_programada ASC
        LIMIT 8
    """):
        data["recordatorios_pendientes"].append({
            "id_recordatorio": fila[0],
            "canal": fila[1],
            "tipo_recordatorio": fila[2],
            "destinatario": fila[3],
            "mensaje": fila[4],
            "fecha_programada": str(fila[5]) if fila[5] else '',
            "estado_envio": fila[6],
        })

    for fila in fetchall("""
        SELECT p.id_pago, pa.nombres, pa.apellidos, p.monto, p.fecha_pago, COALESCE(tp.nombre_tipo_pago, 'Sin tipo')
        FROM pagos p
        LEFT JOIN pacientes pa ON p.id_paciente = pa.id_paciente
        LEFT JOIN tipos_pago tp ON p.id_tipo_pago = tp.id_tipo_pago
        WHERE p.fecha_pago IS NOT NULL
          AND MONTH(p.fecha_pago) = MONTH(CURDATE())
          AND YEAR(p.fecha_pago) = YEAR(CURDATE())
        ORDER BY p.fecha_pago DESC, p.id_pago DESC
        LIMIT 8
    """):
        data["pagos_recientes"].append({
            "id_pago": fila[0],
            "paciente": f"{fila[1] or ''} {fila[2] or ''}".strip(),
            "monto": float(fila[3] or 0),
            "fecha_pago": fila[4].strftime('%Y-%m-%d %H:%M') if fila[4] else '',
            "tipo_pago": fila[5] or ''
        })

    for fila in fetchall("""
        SELECT c.id_cita, pa.nombres, pa.apellidos, ud.nombres, ud.apellidos, c.fecha_cita, c.hora_inicio,
               COALESCE(e.nombre_estado, 'Sin estado') AS estado
        FROM citas c
        LEFT JOIN pacientes pa ON c.id_paciente = pa.id_paciente
        LEFT JOIN doctores d ON c.id_doctor = d.id_doctor
        LEFT JOIN usuarios ud ON d.id_usuario = ud.id_usuario
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita ASC, c.hora_inicio ASC
        LIMIT 8
    """):
        data["citas_proximas"].append({
            "id_cita": fila[0],
            "paciente": f"{fila[1] or ''} {fila[2] or ''}".strip(),
            "doctor": f"{fila[3] or ''} {fila[4] or ''}".strip(),
            "fecha_cita": str(fila[5]) if fila[5] else '',
            "hora_inicio": str(fila[6])[:5] if fila[6] else '',
            "estado": fila[7] or ''
        })

    for fila in fetchall("""
        SELECT c.id_cita, pa.nombres, pa.apellidos, c.fecha_cita, c.hora_inicio, COALESCE(e.nombre_estado, 'Sin estado')
        FROM citas c
        LEFT JOIN pagos p ON c.id_cita = p.id_cita
        LEFT JOIN pacientes pa ON c.id_paciente = pa.id_paciente
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita < CURDATE()
          AND p.id_pago IS NULL
          AND (e.nombre_estado IS NULL OR LOWER(e.nombre_estado) NOT IN ('cancelada', 'cancelado'))
        ORDER BY c.fecha_cita DESC, c.hora_inicio DESC
        LIMIT 8
    """):
        data["pacientes_pendientes_pago"].append({
            "id_cita": fila[0],
            "paciente": f"{fila[1] or ''} {fila[2] or ''}".strip(),
            "fecha_cita": str(fila[3]) if fila[3] else '',
            "hora_inicio": str(fila[4])[:5] if fila[4] else '',
            "estado": fila[5] or ''
        })

    for fila in fetchall("""
        SELECT COALESCE(e.nombre_estado, 'Sin estado') AS estado, COUNT(c.id_cita) AS total
        FROM citas c
        LEFT JOIN estados_cita e ON c.id_estado_cita = e.id_estado_cita
        WHERE c.fecha_cita IS NOT NULL
          AND MONTH(c.fecha_cita) = MONTH(CURDATE())
          AND YEAR(c.fecha_cita) = YEAR(CURDATE())
        GROUP BY estado
        ORDER BY total DESC
    """):
        data["citas_estado_mes"].append({
            "estado": fila[0] or 'Sin estado',
            "total": int(fila[1] or 0)
        })

    return JsonResponse(data, json_dumps_params={'ensure_ascii': False})