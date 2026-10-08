from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Expediente
from django.urls import reverse_lazy

# Create your views here.

class ExpedienteListView(LoginRequiredMixin, ListView):
    model = Expediente
    template_name = "expedientes/expediente_list.html"
    context_object_name = "expedientes"
    
    def get_queryset(self):
        qs = Expediente.objects.filter(owner=self.request.user)
        q = self.request.GET.get("q", "")
        qs = qs.filter(numero__icontains=q) | qs.filter(caratula__icontains=q) | qs.filter(fuero_juzgado__icontains=q) | qs.filter(tipo_proceso__icontains=q) | qs.filter(observaciones__icontains=q)
        return qs

class ExpedienteDetailView(LoginRequiredMixin, DetailView):
    model = Expediente
    template_name = "expedientes/expediente_detail.html"

    
    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)
    
class ExpedienteCreateView(LoginRequiredMixin, CreateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class ExpedienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Expediente
    template_name = "expedientes/expediente_form.html"
    fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']

    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)
    
class ExpedienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Expediente
    template_name = "expedientes/expediente_confirm_delete.html"
    success_url = reverse_lazy('expedientes:lista')

    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)