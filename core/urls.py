from django.urls import path
from . import views

urlpatterns = [
    # Login / logout
    path('', views.login_page, name='login'),
    path('login/', views.login_page, name='login'),
    path('api/login/', views.login_json, name='login_json'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard_page, name='dashboard'),
    path('api/dashboard/', views.api_dashboard_recordatorios, name='api_dashboard_recordatorios'),

    # Pacientes
    path('pacientes/', views.pacientes_page, name='pacientes'),
    path('api/pacientes/', views.pacientes_json, name='pacientes_json'),
    path('api/pacientes/crear/', views.crear_paciente_json, name='crear_paciente_json'),
    path('api/pacientes/<int:id_paciente>/actualizar/', views.actualizar_paciente_json, name='actualizar_paciente_json'),
    path('api/pacientes/<int:id_paciente>/desactivar/', views.desactivar_paciente_json, name='desactivar_paciente_json'),
    path('api/pacientes/<int:id_paciente>/activar/', views.activar_paciente_json, name='activar_paciente_json'),
    path('pacientes/<int:id_paciente>/word/', views.generar_word_paciente, name='generar_word_paciente'),

    # Citas
    path('citas/', views.citas_page, name='citas'),
    path('api/citas/', views.citas_json, name='citas_json'),
    path('api/citas/catalogos/', views.catalogos_citas_json, name='catalogos_citas_json'),
    path('api/citas/crear/', views.crear_cita_json, name='crear_cita_json'),
    path('api/citas/<int:id_cita>/editar/', views.editar_cita_json, name='editar_cita_json'),
    path('api/citas/<int:id_cita>/cancelar/', views.cancelar_cita_json, name='cancelar_cita_json'),

    # Pagos
    path('pagos/', views.pagos_page, name='pagos'),
    path('api/pagos/', views.pagos_json, name='pagos_json'),
    path('api/pagos/catalogos/', views.pagos_catalogos_json, name='pagos_catalogos_json'),
    path('api/pagos/crear/', views.crear_pago_json, name='crear_pago_json'),

    # Notas clínicas
    path('notas/', views.notas_page, name='notas'),
    path('api/notas/', views.notas_json, name='notas_json'),
    path('api/notas/catalogos/', views.notas_catalogos_json, name='notas_catalogos_json'),
    path('api/notas/crear/', views.crear_nota_json, name='crear_nota_json'),

    # Doctores
    path('doctores/', views.doctores_page, name='doctores'),
    path('api/doctores/', views.doctores_json, name='doctores_json'),
    path('api/doctores/catalogos/', views.doctores_catalogos_json, name='doctores_catalogos_json'),
    path('api/doctores/crear/', views.crear_doctor_json, name='crear_doctor_json'),
    path('api/doctores/<int:id_doctor>/actualizar/', views.actualizar_doctor_json, name='actualizar_doctor_json'),
    path('api/doctores/<int:id_doctor>/desactivar/', views.desactivar_doctor_json, name='desactivar_doctor_json'),
    path('api/doctores/<int:id_doctor>/activar/', views.activar_doctor_json, name='activar_doctor_json'),

    # Usuarios
    path('usuarios/', views.usuarios_page, name='usuarios'),
    path('api/usuarios/', views.usuarios_json, name='usuarios_json'),
    path('api/usuarios/catalogos/', views.usuarios_catalogos_json, name='usuarios_catalogos_json'),
    path('api/usuarios/crear/', views.crear_usuario_json, name='crear_usuario_json'),
    path('api/usuarios/<int:id_usuario>/actualizar/', views.actualizar_usuario_json, name='actualizar_usuario_json'),
    path('api/usuarios/<int:id_usuario>/desactivar/', views.desactivar_usuario_json, name='desactivar_usuario_json'),
    path('api/usuarios/<int:id_usuario>/activar/', views.activar_usuario_json, name='activar_usuario_json'),

    # Roles
    # path('roles/', views.roles_page, name='roles'),
    # path('api/roles/', views.roles_json, name='roles_json'),
    # path('api/roles/crear/', views.crear_rol_json, name='crear_rol_json'),
    # path('api/roles/<int:id_rol>/actualizar/', views.actualizar_rol_json, name='actualizar_rol_json'),
    # path('api/roles/<int:id_rol>/desactivar/', views.desactivar_rol_json, name='desactivar_rol_json'),
    # path('api/roles/<int:id_rol>/activar/', views.activar_rol_json, name='activar_rol_json'),

    # Configuración
    path('configuracion/', views.configuracion_page, name='configuracion'),
    path('api/configuracion/', views.configuracion_json, name='configuracion_json'),
    path('api/configuracion/actualizar/', views.actualizar_configuracion_json, name='actualizar_configuracion_json'),

    # Reportes
    # path('reportes/', views.reportes_page, name='reportes'),
    # path('api/reportes/', views.reportes_json, name='reportes_json'),
    # path('reportes/word/', views.generar_word_reporte_general, name='generar_word_reporte_general'),

    # Recordatorios
    path('recordatorios/generar/', views.generar_recordatorios_automaticos, name='generar_recordatorios_automaticos'),
    path('recordatorios/enviar-correo/', views.enviar_recordatorios_correo, name='enviar_recordatorios_correo'),
    path('recordatorios/whatsapp/', views.listar_recordatorios_whatsapp, name='listar_recordatorios_whatsapp'),
    path('recordatorios/whatsapp/<int:id_recordatorio>/abrir/', views.abrir_recordatorio_whatsapp, name='abrir_recordatorio_whatsapp'),
]