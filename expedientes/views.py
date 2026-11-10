import os

from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import ArchivoAdjunto, Expediente, Gasto, Honorario, Parte, PasoProcesal, Vencimiento
from .forms import (
    AdjuntoForm, ExpedienteForm, GastoForm, HonorarioForm, ParteForm, PasoProcesalForm, VencimientoForm,
)
from django.urls import reverse_lazy

# Create your views here.

class ExpedientePropioMixin(LoginRequiredMixin):
    """Exige sesión y limita la vista a los expedientes del usuario."""

    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)

class ExpedienteListView(ExpedientePropioMixin, ListView):
    model = Expediente
    template_name = "expedientes/expediente_list.html"
    context_object_name = "expedientes"
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "")
        estado = self.request.GET.get("estado", "")
        qs = qs.filter(numero__icontains=q) | qs.filter(caratula__icontains=q) | qs.filter(fuero_juzgado__icontains=q) | qs.filter(tipo_proceso__icontains=q) | qs.filter(observaciones__icontains=q)
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estados"] = Expediente.Estado.choices
        return context


class ExpedienteDetailView(ExpedientePropioMixin, DetailView):
    model = Expediente
    template_name = "expedientes/expediente_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Un total por moneda: nunca se suman pesos con dólares.
        context["totales_honorarios"] = (
            self.object.honorarios.values("moneda").annotate(total=Sum("monto")).order_by("moneda")
        )
        context["totales_gastos"] = (
            self.object.gastos.values("moneda").annotate(total=Sum("monto")).order_by("moneda")
        )
        return context

class ExpedienteCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    form_class = ExpedienteForm
    success_message = "Expediente creado."

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs

class ExpedienteUpdateView(ExpedientePropioMixin, SuccessMessageMixin, UpdateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    form_class = ExpedienteForm
    success_message = "Cambios guardados."



    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs

class ExpedienteDeleteView(ExpedientePropioMixin, SuccessMessageMixin, DeleteView):
    model = Expediente
    template_name = "expedientes/expediente_confirm_delete.html"
    success_url = reverse_lazy('expedientes:lista')
    success_message = "Expediente eliminado."


# --- Entidades asociadas a un expediente -------------------------------------

class HijoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """Alta de una entidad que cuelga de un expediente del usuario."""
    template_name = "expedientes/hijo_form.html"
    success_message = "Guardado."

    @cached_property
    def expediente(self):
        # 404 si el expediente de la URL no existe o es de otro usuario.
        return get_object_or_404(
            Expediente, pk=self.kwargs["expediente_pk"], owner=self.request.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["expediente"] = self.expediente
        return context

    def form_valid(self, form):
        # El expediente se asigna en el servidor, igual que owner.
        form.instance.expediente = self.expediente
        return super().form_valid(form)

    def get_success_url(self):
        return self.expediente.get_absolute_url()


class HijoPropioMixin(LoginRequiredMixin, SuccessMessageMixin):
    """Para editar y eliminar: el dueño se alcanza a través del expediente."""

    def get_queryset(self):
        return self.model.objects.filter(expediente__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["expediente"] = self.object.expediente
        return context

    def get_success_url(self):
        return self.object.expediente.get_absolute_url()


class HijoUpdateView(HijoPropioMixin, UpdateView):
    template_name = "expedientes/hijo_form.html"
    success_message = "Cambios guardados."


class HijoDeleteView(HijoPropioMixin, DeleteView):
    template_name = "expedientes/hijo_confirm_delete.html"
    success_message = "Eliminado."


class ParteCreateView(HijoCreateView):
    model = Parte
    form_class = ParteForm
    titulo = "Nueva parte"


class ParteUpdateView(HijoUpdateView):
    model = Parte
    form_class = ParteForm
    titulo = "Editar parte"


class ParteDeleteView(HijoDeleteView):
    model = Parte
    titulo = "Eliminar parte"


class PasoCreateView(HijoCreateView):
    model = PasoProcesal
    form_class = PasoProcesalForm
    titulo = "Nuevo paso procesal"


class PasoUpdateView(HijoUpdateView):
    model = PasoProcesal
    form_class = PasoProcesalForm
    titulo = "Editar paso procesal"


class PasoDeleteView(HijoDeleteView):
    model = PasoProcesal
    titulo = "Eliminar paso procesal"


class VencimientoCreateView(HijoCreateView):
    model = Vencimiento
    form_class = VencimientoForm
    titulo = "Nuevo vencimiento"


class VencimientoUpdateView(HijoUpdateView):
    model = Vencimiento
    form_class = VencimientoForm
    titulo = "Editar vencimiento"


class VencimientoDeleteView(HijoDeleteView):
    model = Vencimiento
    titulo = "Eliminar vencimiento"


class VencimientoListView(LoginRequiredMixin, ListView):
    """Panel: vencimientos pendientes de todos los expedientes del usuario."""
    template_name = "expedientes/vencimiento_list.html"
    context_object_name = "vencimientos"

    def get_queryset(self):
        # El dueño se alcanza a través del expediente, como en HijoPropioMixin.
        # select_related trae el expediente en la misma consulta (evita N+1).
        # El orden por fecha lo da Meta.ordering del modelo.
        return Vencimiento.objects.filter(
            expediente__owner=self.request.user,
            estado=Vencimiento.Estado.PENDIENTE,
        ).select_related("expediente")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vencimientos = context["vencimientos"]
        context["cantidad_vencidos"] = sum(1 for v in vencimientos if v.esta_vencido)
        context["cantidad_proximos"] = sum(1 for v in vencimientos if v.vence_pronto)
        context["dias_aviso"] = Vencimiento.DIAS_AVISO
        return context


class VencimientoCumplirView(LoginRequiredMixin, View):
    """Acción rápida: solo POST (un GET responde 405)."""

    def post(self, request, pk):
        vencimiento = get_object_or_404(
            Vencimiento, pk=pk, expediente__owner=request.user
        )
        vencimiento.estado = Vencimiento.Estado.CUMPLIDO
        vencimiento.save(update_fields=["estado"])
        messages.success(request, "Vencimiento marcado como cumplido.")
        # Se compara contra un valor fijo: nunca se redirige a una URL que mande el usuario.
        if request.POST.get("volver") == "panel":
            return redirect("expedientes:vencimientos")
        return redirect(vencimiento.expediente)


class HonorarioCreateView(HijoCreateView):
    model = Honorario
    form_class = HonorarioForm
    titulo = "Nuevo honorario"


class HonorarioUpdateView(HijoUpdateView):
    model = Honorario
    form_class = HonorarioForm
    titulo = "Editar honorario"


class HonorarioDeleteView(HijoDeleteView):
    model = Honorario
    titulo = "Eliminar honorario"


class GastoCreateView(HijoCreateView):
    model = Gasto
    form_class = GastoForm
    titulo = "Nuevo gasto"


class GastoUpdateView(HijoUpdateView):
    model = Gasto
    form_class = GastoForm
    titulo = "Editar gasto"


class GastoDeleteView(HijoDeleteView):
    model = Gasto
    titulo = "Eliminar gasto"


# --- Archivos adjuntos ---------------------------------------------------------

class AdjuntoCreateView(HijoCreateView):
    model = ArchivoAdjunto
    form_class = AdjuntoForm
    titulo = "Adjuntar archivo"
    success_message = "Archivo adjuntado."


class AdjuntoDeleteView(HijoDeleteView):
    model = ArchivoAdjunto
    titulo = "Eliminar adjunto"
    # El archivo del disco lo borra la señal post_delete (models.py).


class AdjuntoDescargarView(LoginRequiredMixin, View):
    """Sirve el archivo a través de una vista: pide sesión y verifica el dueño.

    Nunca se expone /media/ directamente: esa URL no pasaría por ningún control.
    """

    def get(self, request, pk):
        adjunto = get_object_or_404(
            ArchivoAdjunto, pk=pk, expediente__owner=request.user
        )
        try:
            archivo = adjunto.archivo.open("rb")
        except FileNotFoundError:
            # El registro existe pero el archivo ya no está en el disco.
            raise Http404("El archivo no está disponible.")
        return FileResponse(
            archivo,
            as_attachment=True,
            filename=os.path.basename(adjunto.archivo.name),
        )
