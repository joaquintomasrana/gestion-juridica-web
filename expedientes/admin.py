from django.contrib import admin
from .models import Expediente, Parte, PasoProcesal, Vencimiento, Honorario, Gasto, ArchivoAdjunto


class ParteInline(admin.TabularInline):
    model = Parte
    extra = 1


class PasoProcesalInline(admin.TabularInline):
    model = PasoProcesal
    extra = 1


class VencimientoInline(admin.TabularInline):
    model = Vencimiento
    extra = 1


class HonorarioInline(admin.TabularInline):
    model = Honorario
    extra = 1


class GastoInline(admin.TabularInline):
    model = Gasto
    extra = 1


class ArchivoAdjuntoInline(admin.TabularInline):
    model = ArchivoAdjunto
    extra = 1


@admin.register(Expediente)
class ExpedienteAdmin(admin.ModelAdmin):
    inlines = [
        ParteInline,
        PasoProcesalInline,
        VencimientoInline,
        HonorarioInline,
        GastoInline,
        ArchivoAdjuntoInline,
    ]
    list_display = ("numero", "caratula", "estado", "owner", "creado")
    list_filter = ("estado", "owner")
    search_fields = ("numero", "caratula")
    
@admin.register(Vencimiento)
class VencimientoAdmin(admin.ModelAdmin):
    list_display = ("expediente", "fecha", "descripcion", "estado")
    list_filter = ("estado",)