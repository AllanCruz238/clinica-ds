
from django.db import models


class Auditoria(models.Model):
    id_auditoria = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey('Usuarios', models.DO_NOTHING, db_column='id_usuario', blank=True, null=True)
    tabla_afectada = models.CharField(max_length=100, blank=True, null=True)
    id_registro_afectado = models.IntegerField(blank=True, null=True)
    accion = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    fecha_evento = models.DateTimeField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'auditoria'


class Citas(models.Model):
    id_cita = models.AutoField(primary_key=True)
    id_paciente = models.ForeignKey('Pacientes', models.DO_NOTHING, db_column='id_paciente', blank=True, null=True)
    id_doctor = models.ForeignKey('Doctores', models.DO_NOTHING, db_column='id_doctor', blank=True, null=True)
    id_motivo_consulta = models.ForeignKey('MotivosConsulta', models.DO_NOTHING, db_column='id_motivo_consulta', blank=True, null=True)
    id_estado_cita = models.ForeignKey('EstadosCita', models.DO_NOTHING, db_column='id_estado_cita', blank=True, null=True)
    fecha_cita = models.DateField(blank=True, null=True)
    hora_inicio = models.TimeField(blank=True, null=True)
    hora_fin = models.TimeField(blank=True, null=True)
    modalidad = models.CharField(max_length=20, blank=True, null=True)
    razon_consulta_detalle = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    creada_por = models.ForeignKey('Usuarios', models.DO_NOTHING, db_column='creada_por', blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        paciente = str(self.id_paciente) if self.id_paciente else f"Paciente {self.id_paciente_id}"
        fecha = self.fecha_cita if self.fecha_cita else "Sin fecha"
        return f"Cita {self.id_cita} - {paciente} - {fecha}"

    class Meta:
        #managed = False
        db_table = 'citas'


class Doctores(models.Model):
    id_doctor = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey('Usuarios', models.DO_NOTHING, db_column='id_usuario', blank=True, null=True)
    id_especialidad = models.ForeignKey('Especialidades', models.DO_NOTHING, db_column='id_especialidad', blank=True, null=True)
    numero_colegiado = models.CharField(max_length=50, blank=True, null=True)
    duracion_cita_minutos = models.IntegerField(blank=True, null=True)
    color_agenda = models.CharField(max_length=7, blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        if self.id_usuario:
            return f"Dr(a). {self.id_usuario.nombres or ''} {self.id_usuario.apellidos or ''}".strip()
        return f"Doctor {self.id_doctor}"

    class Meta:
        #managed = False
        db_table = 'doctores'


class Especialidades(models.Model):
    id_especialidad = models.AutoField(primary_key=True)
    nombre_especialidad = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nombre_especialidad

    class Meta:
        #managed = False
        db_table = 'especialidades'


class EstadosCita(models.Model):
    id_estado_cita = models.AutoField(primary_key=True)
    nombre_estado = models.CharField(max_length=50)
    color_hex = models.CharField(max_length=7, blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nombre_estado

    class Meta:
        #managed = False
        db_table = 'estados_cita'


class MotivosConsulta(models.Model):
    id_motivo_consulta = models.AutoField(primary_key=True)
    nombre_motivo = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nombre_motivo

    class Meta:
        #managed = False
        db_table = 'motivos_consulta'


class NotasClinicas(models.Model):
    id_nota_clinica = models.AutoField(primary_key=True)
    id_paciente = models.ForeignKey('Pacientes', models.DO_NOTHING, db_column='id_paciente', blank=True, null=True)
    id_cita = models.ForeignKey(Citas, models.DO_NOTHING, db_column='id_cita', blank=True, null=True)
    id_doctor = models.ForeignKey(Doctores, models.DO_NOTHING, db_column='id_doctor', blank=True, null=True)
    titulo = models.CharField(max_length=200, blank=True, null=True)
    contenido = models.TextField(blank=True, null=True)
    recomendaciones = models.TextField(blank=True, null=True)
    fecha_nota = models.DateTimeField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'notas_clinicas'


class Pacientes(models.Model):
    id_paciente = models.AutoField(primary_key=True)
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    sexo = models.CharField(max_length=10, blank=True, null=True)
    dpi_pasaporte = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    correo = models.CharField(max_length=100, blank=True, null=True)
    ocupacion = models.CharField(max_length=100, blank=True, null=True)
    contacto_emergencia_nombre = models.CharField(max_length=100, blank=True, null=True)
    contacto_emergencia_telefono = models.CharField(max_length=20, blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)
    fecha_registro = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombres or ''} {self.apellidos or ''}".strip()

    class Meta:
        #managed = False
        db_table = 'pacientes'


class Pagos(models.Model):
    id_pago = models.AutoField(primary_key=True)
    id_paciente = models.ForeignKey(Pacientes, models.DO_NOTHING, db_column='id_paciente', blank=True, null=True)
    id_cita = models.ForeignKey(Citas, models.DO_NOTHING, db_column='id_cita', blank=True, null=True)
    id_tipo_pago = models.ForeignKey('TiposPago', models.DO_NOTHING, db_column='id_tipo_pago', blank=True, null=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fecha_pago = models.DateTimeField(blank=True, null=True)
    referencia_pago = models.CharField(max_length=100, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'pagos'


class Recordatorios(models.Model):
    id_recordatorio = models.AutoField(primary_key=True)
    id_cita = models.ForeignKey(Citas, models.DO_NOTHING, db_column='id_cita', blank=True, null=True)
    canal = models.CharField(max_length=20, blank=True, null=True)
    tipo_recordatorio = models.CharField(max_length=50, blank=True, null=True)
    destinatario = models.CharField(max_length=100, blank=True, null=True)
    mensaje = models.TextField(blank=True, null=True)
    fecha_programada = models.DateTimeField(blank=True, null=True)
    fecha_envio = models.DateTimeField(blank=True, null=True)
    estado_envio = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'recordatorios'


class Roles(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nombre_rol or f"Rol {self.id_rol}"

    class Meta:
        #managed = False
        db_table = 'roles'


class TiposPago(models.Model):
    id_tipo_pago = models.AutoField(primary_key=True)
    nombre_tipo_pago = models.CharField(max_length=50)
    activo = models.IntegerField(blank=True, null=True)

    class Meta:
        #managed = False
        db_table = 'tipos_pago'


class Usuarios(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(Roles, models.DO_NOTHING, db_column='id_rol', blank=True, null=True)
    username = models.CharField(unique=True, max_length=50)
    password_hash = models.CharField(max_length=255)
    correo = models.CharField(unique=True, max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    nombres = models.CharField(max_length=100, blank=True, null=True)
    apellidos = models.CharField(max_length=100, blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(blank=True, null=True)
    ultimo_acceso = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombres or ''} {self.apellidos or ''} ({self.username})".strip()

    class Meta:
        #managed = False
        db_table = 'usuarios'


class ConfiguracionClinica(models.Model):
    id_configuracion = models.AutoField(primary_key=True)
    nombre_clinica = models.CharField(max_length=150)
    slogan = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    correo = models.CharField(max_length=120, blank=True, null=True)
    sitio_web = models.CharField(max_length=150, blank=True, null=True)
    logo_url = models.TextField(blank=True, null=True)
    color_primario = models.CharField(max_length=20, blank=True, null=True)
    color_secundario = models.CharField(max_length=20, blank=True, null=True)
    activo = models.IntegerField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.nombre_clinica

    class Meta:
        #managed = False
        db_table = 'configuracion_clinica'