from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from expedientes.models import (
    Expediente,
    Gasto,
    Honorario,
    Moneda,
    Parte,
    PasoProcesal,
    Vencimiento,
)

User = get_user_model()

CLAVE_DEMO = "demo-gestion-2026"

# Todos los nombres, números y domicilios son inventados.
ACTORES = ["Gómez, Marta", "Ledesma, Rubén", "Sosa, Claudia", "Ferreyra, Hugo",
           "Medina, Paula", "Acosta, Darío", "Ríos, Silvia", "Vera, Tomás"]
DEMANDADOS = ["Pérez, Luis", "Transportes del Sur SRL", "Molina, Andrea", "Seguros La Previsora SA",
              "Quiroga, Néstor", "Consorcio Av. Ficticia 123", "Herrera, Julia", "Constructora Andina SA"]
PROCESOS = ["Daños y perjuicios", "Cobro de pesos", "Desalojo", "Despido", "Sucesión", "Alimentos"]
FUEROS = ["Civil N.° 3", "Comercial N.° 7", "Laboral N.° 12", "Familia N.° 2"]
ESTADOS = [Expediente.Estado.ACTIVO, Expediente.Estado.ACTIVO, Expediente.Estado.ARCHIVADO, Expediente.Estado.CERRADO]
PASOS = ["Presentación de demanda", "Traslado de la demanda", "Contestación de demanda", "Apertura a prueba"]

# Días contados desde hoy: da vencidos, próximos y lejanos para probar el panel.
DIAS_VENCIMIENTOS = [-5, 3, 20]


class Command(BaseCommand):
    help = "Borra y vuelve a crear los usuarios de demostración con datos ficticios."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Solo se ejecuta con DEBUG=True: la clave demo es pública.")

        # El CASCADE borra también sus expedientes y entidades asociadas.
        User.objects.filter(username__in=["ana.demo", "beto.demo"]).delete()

        ana = User.objects.create_user("ana.demo", password=CLAVE_DEMO)
        beto = User.objects.create_user("beto.demo", password=CLAVE_DEMO)
        self.crear_expedientes(ana, cantidad=12, inicio=0)
        self.crear_expedientes(beto, cantidad=4, inicio=12)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: ana.demo (12 expedientes) y beto.demo (4). Clave: {CLAVE_DEMO}"
        ))

    def crear_expedientes(self, usuario, cantidad, inicio):
        hoy = timezone.localdate()
        for i in range(inicio, inicio + cantidad):
            actor = ACTORES[i % len(ACTORES)]
            demandado = DEMANDADOS[i % len(DEMANDADOS)]
            proceso = PROCESOS[i % len(PROCESOS)]
            fecha_inicio = hoy - timedelta(days=60 + i * 25)

            expediente = Expediente.objects.create(
                owner=usuario,
                # El último de cada usuario queda sin número, un caso válido.
                numero=None if i == inicio + cantidad - 1 else f"{1000 + i}/2026",
                caratula=f"{actor} c/ {demandado} s/ {proceso.lower()}",
                fuero_juzgado=FUEROS[i % len(FUEROS)],
                fecha_inicio=fecha_inicio,
                tipo_proceso=proceso,
                estado=ESTADOS[i % len(ESTADOS)],
                observaciones="Expediente ficticio de demostración.",
            )

            Parte.objects.create(
                expediente=expediente,
                nombre=actor,
                tipo=Parte.Tipo.ACTOR,
                dni_cuit=f"{20000000 + i}",
                domicilio=f"Calle Ficticia {100 + i}",
                email=f"parte{i}@example.com",
            )
            Parte.objects.create(expediente=expediente, nombre=demandado, tipo=Parte.Tipo.DEMANDADO)

            for orden, descripcion in enumerate(PASOS):
                PasoProcesal.objects.create(
                    expediente=expediente,
                    fecha=fecha_inicio + timedelta(days=orden * 12),
                    descripcion=descripcion,
                )

            for dias in DIAS_VENCIMIENTOS:
                Vencimiento.objects.create(
                    expediente=expediente,
                    fecha=hoy + timedelta(days=dias + i % 3),
                    descripcion=f"Vencimiento de plazo procesal ({proceso.lower()})",
                )
            Vencimiento.objects.create(
                expediente=expediente,
                fecha=hoy - timedelta(days=15),
                descripcion="Audiencia preliminar",
                estado=Vencimiento.Estado.CUMPLIDO,
            )

            Honorario.objects.create(
                expediente=expediente,
                fecha=fecha_inicio,
                monto=Decimal("150000.00") + i * 10000,
                concepto="Anticipo de honorarios",
                forma_pago="Transferencia",
            )
            Honorario.objects.create(
                expediente=expediente,
                fecha=fecha_inicio + timedelta(days=30),
                monto=Decimal("500.00"),
                moneda=Moneda.USD,
                concepto="Consulta inicial",
            )

            Gasto.objects.create(
                expediente=expediente,
                fecha=fecha_inicio,
                monto=Decimal("35000.00"),
                descripcion="Tasa de justicia",
            )
