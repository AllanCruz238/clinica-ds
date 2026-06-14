from django.core.management.base import BaseCommand
from django.db import connection


TIPOS_MANUALES = ['manual_dashboard', 'manual_dashboard_doctor']


class Command(BaseCommand):
    help = 'Elimina recordatorios generados manualmente desde el dashboard (tipo_recordatorio = manual_dashboard / manual_dashboard_doctor)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Ejecuta el borrado real. Sin este flag solo muestra los registros que se borrarían.',
        )

    def handle(self, *args, **options):
        placeholders = ', '.join(['%s'] * len(TIPOS_MANUALES))

        # 1. Mostrar cuántos hay y sus IDs
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT id_recordatorio, canal, tipo_recordatorio, destinatario, estado_envio, fecha_programada "
                f"FROM recordatorios WHERE tipo_recordatorio IN ({placeholders}) ORDER BY id_recordatorio",
                TIPOS_MANUALES
            )
            filas = cursor.fetchall()

        total = len(filas)

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No hay registros con tipo_recordatorio manual_dashboard. Nada que borrar.'))
            return

        self.stdout.write(self.style.WARNING(f'\n{total} registro(s) encontrados con tipo manual_dashboard:\n'))
        self.stdout.write(f'{"ID":<6} {"Canal":<10} {"Tipo":<30} {"Destinatario":<35} {"Estado":<12} Fecha')
        self.stdout.write('-' * 110)
        for fila in filas:
            id_rec, canal, tipo, dest, estado, fecha = fila
            self.stdout.write(f'{id_rec:<6} {(canal or ""):<10} {(tipo or ""):<30} {(dest or ""):<35} {(estado or ""):<12} {fecha}')

        ids = [f[0] for f in filas]
        self.stdout.write(f'\nIDs a eliminar: {ids}\n')

        # 2. Contar total actual
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM recordatorios')
            total_antes = cursor.fetchone()[0]

        self.stdout.write(f'Total de recordatorios en la BD ahora: {total_antes}')
        self.stdout.write(f'Se eliminarían: {total}')
        self.stdout.write(f'Quedarían: {total_antes - total}\n')

        if not options['confirmar']:
            self.stdout.write(self.style.NOTICE(
                'Modo simulación (--dry-run). Para borrar de verdad ejecuta:\n'
                '  python manage.py limpiar_recordatorios --confirmar\n'
            ))
            return

        # 3. Borrar
        with connection.cursor() as cursor:
            cursor.execute(
                f'DELETE FROM recordatorios WHERE tipo_recordatorio IN ({placeholders})',
                TIPOS_MANUALES
            )
            eliminados = cursor.rowcount

        # 4. Verificar
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM recordatorios')
            total_despues = cursor.fetchone()[0]

        self.stdout.write(self.style.SUCCESS(
            f'\nBorrado completado.\n'
            f'  Eliminados : {eliminados}\n'
            f'  Quedan     : {total_despues}\n'
        ))
