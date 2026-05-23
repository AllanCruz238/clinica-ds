from django.contrib import admin
from .models import *

admin.site.register(Usuarios)
admin.site.register(Pacientes)
admin.site.register(Doctores)
admin.site.register(Citas)
admin.site.register(NotasClinicas)
admin.site.register(Pagos)
admin.site.register(Recordatorios)
admin.site.register(Roles)
admin.site.register(TiposPago)
admin.site.register(Especialidades)
admin.site.register(EstadosCita)
admin.site.register(MotivosConsulta)