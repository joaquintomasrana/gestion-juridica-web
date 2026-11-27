from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone


class Moneda(models.TextChoices):
    ARS = "ARS", "Pesos (ARS)"
    USD = "USD", "Dólares (USD)"


class Expediente(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        ARCHIVADO = "archivado", "Archivado"
        CERRADO = "cerrado", "Cerrado"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expedientes",
        verbose_name="titular",
    )
    numero = models.CharField("número", max_length=100, blank=True, null=True)
    caratula = models.CharField("carátula", max_length=300)
    fuero_juzgado = models.CharField("fuero / juzgado", max_length=200, blank=True)
    fecha_inicio = models.DateField("fecha de inicio", blank=True, null=True)
    tipo_proceso = models.CharField("tipo de proceso", max_length=100, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        # Primero los que tuvieron actividad más reciente (ver las señales al final).
        # "-pk" desempata: sin un orden único, la paginación podría repetir u
        # omitir expedientes con la misma fecha entre una página y otra.
        ordering = ["-actualizado", "-pk"]
        verbose_name = "expediente"
        verbose_name_plural = "expedientes"
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "numero"],
                condition=models.Q(numero__isnull=False),
                name="numero_unico_por_titular",
            )
        ]

    def __str__(self):
        return f"{self.numero or 's/n'} — {self.caratula}"

    def save(self, *args, **kwargs):
        # Un número vacío se guarda como NULL, no como cadena vacía,
        # para que la restricción de unicidad (por titular) permita varios
        # expedientes "sin número" para un mismo usuario.
        if not self.numero:
            self.numero = None
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("expedientes:detalle", kwargs={"pk": self.pk})


class Parte(models.Model):
    class Tipo(models.TextChoices):
        ACTOR = "actor", "Actor"
        DEMANDADO = "demandado", "Demandado"
        TERCERO = "tercero", "Tercero"
        OTRO = "otro", "Otro"

    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="partes")
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.ACTOR)
    dni_cuit = models.CharField("DNI / CUIT", max_length=20, blank=True)
    domicilio = models.CharField(max_length=300, blank=True)
    telefono = models.CharField("teléfono", max_length=50, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()})"


class PasoProcesal(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="pasos")
    fecha = models.DateField()
    descripcion = models.CharField("descripción", max_length=300)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "paso procesal"
        verbose_name_plural = "pasos procesales"

    def __str__(self):
        return f"{self.fecha} — {self.descripcion}"


class Vencimiento(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        CUMPLIDO = "cumplido", "Cumplido"


    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="vencimientos")
    fecha = models.DateField()
    descripcion = models.CharField("descripción", max_length=300)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.fecha} — {self.descripcion}"

    # Cuántos días antes se avisa que un vencimiento está cerca.
    DIAS_AVISO = 7

    @property
    def esta_vencido(self):
        return self.estado == self.Estado.PENDIENTE and self.fecha < timezone.localdate()

    @property
    def vence_pronto(self):
        """Pendiente y dentro de los próximos DIAS_AVISO días (hoy incluido)."""
        hoy = timezone.localdate()
        return (
            self.estado == self.Estado.PENDIENTE
            and hoy <= self.fecha <= hoy + timedelta(days=self.DIAS_AVISO)
        )


class Honorario(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="honorarios")
    fecha = models.DateField()
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.ARS)
    concepto = models.CharField(max_length=200, blank=True)
    forma_pago = models.CharField("forma de pago", max_length=100, blank=True)

    def __str__(self):
        return f"{self.monto} {self.moneda} — {self.concepto}"

    class Meta:
        ordering = ["-fecha"]

class Gasto(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="gastos")
    fecha = models.DateField()
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    moneda = models.CharField(max_length=3, choices=Moneda.choices, default=Moneda.ARS)
    descripcion = models.CharField("descripción", max_length=300)

    def __str__(self):
        return f"{self.monto} {self.moneda} — {self.descripcion}"

    class Meta:
        ordering = ["-fecha"]


def ruta_adjunto(instance, filename):
    # Cada archivo se guarda en una carpeta por expediente.
    return f"expedientes/{instance.expediente_id}/{filename}"


class ArchivoAdjunto(models.Model):
    expediente = models.ForeignKey(Expediente, on_delete=models.CASCADE, related_name="adjuntos")
    archivo = models.FileField(upload_to=ruta_adjunto)
    descripcion = models.CharField("descripción", max_length=300, blank=True)
    subido = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-subido"]
        verbose_name = "archivo adjunto"
        verbose_name_plural = "archivos adjuntos"

    def __str__(self):
        return self.descripcion or self.archivo.name


@receiver(post_delete, sender=ArchivoAdjunto)
def borrar_archivo_del_disco(sender, instance, **kwargs):
    # Corre al eliminar un adjunto y también al eliminar su expediente (CASCADE):
    # la base borra el registro, pero el archivo en media/ hay que borrarlo a mano.
    if instance.archivo:
        instance.archivo.delete(save=False)


# --- Última actualización del expediente ---------------------------------------
# "actualizado" usa auto_now, que solo se renueva al guardar el propio expediente.
# Pero casi todo el trabajo diario se guarda en las entidades asociadas (un paso
# nuevo, un vencimiento cumplido, un adjunto). Estas señales hacen que cualquier
# alta, cambio o baja de una de ellas cuente como actividad sobre su expediente,
# venga de donde venga: las vistas, el admin o un comando.

ENTIDADES_DEL_EXPEDIENTE = (Parte, PasoProcesal, Vencimiento, Honorario, Gasto, ArchivoAdjunto)


def marcar_expediente_actualizado(sender, instance, **kwargs):
    # update() escribe una sola columna en la base, sin volver a guardar el
    # expediente entero (ni disparar su save()). Si el expediente se está
    # borrando en cascada, no encuentra la fila y no hace nada.
    Expediente.objects.filter(pk=instance.expediente_id).update(actualizado=timezone.now())


for modelo in ENTIDADES_DEL_EXPEDIENTE:
    post_save.connect(marcar_expediente_actualizado, sender=modelo,
                      dispatch_uid=f"actualizado-al-guardar-{modelo.__name__}")
    post_delete.connect(marcar_expediente_actualizado, sender=modelo,
                        dispatch_uid=f"actualizado-al-borrar-{modelo.__name__}")