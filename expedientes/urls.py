from django.urls import path
from . import views

app_name = 'expedientes'

urlpatterns = [
    path('', views.ExpedienteListView.as_view(), name='lista'),
    path('expediente/<int:pk>/', views.ExpedienteDetailView.as_view(), name='detalle'),
]
