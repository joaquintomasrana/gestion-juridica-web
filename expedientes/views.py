from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Expediente
from .forms import ExpedienteForm
from django.urls import reverse_lazy

# Create your views here.

class ExpedienteListView(LoginRequiredMixin, ListView):
    model = Expediente
    template_name = "expedientes/expediente_list.html"
    context_object_name = "expedientes"
    paginate_by = 10
    
    def get_queryset(self):
        qs = Expediente.objects.filter(owner=self.request.user)
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
    

class ExpedienteDetailView(LoginRequiredMixin, DetailView):
    model = Expediente
    template_name = "expedientes/expediente_detail.html"

    
    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)
    
class ExpedienteCreateView(LoginRequiredMixin, CreateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    form_class = ExpedienteForm

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["owner"] = self.request.user
        return kwargs


class ExpedienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    form_class = ExpedienteForm

    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)
    
    def get_form_kwargs(self):
            kwargs = super().get_form_kwargs()
            kwargs["owner"] = self.request.user
            return kwargs
    
class ExpedienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Expediente
    template_name = "expedientes/expediente_confirm_delete.html"
    success_url = reverse_lazy('expedientes:lista')

    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)