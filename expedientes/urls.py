from django.urls import path
from . import views

app_name = 'expedientes'

urlpatterns = [
    path('', views.ExpedienteListView.as_view(), name='lista'),
    path('expediente/<int:pk>/', views.ExpedienteDetailView.as_view(), name='detalle'),
    path('expediente/nuevo/', views.ExpedienteCreateView.as_view(), name='nuevo'),
    path('expediente/<int:pk>/editar/', views.ExpedienteUpdateView.as_view(), name='editar'),
    path('expediente/<int:pk>/eliminar/', views.ExpedienteDeleteView.as_view(), name='eliminar'),

    # Entidades asociadas: el alta lleva el expediente en la URL;
    # editar y eliminar llevan el pk de la propia entidad.
    path('expediente/<int:expediente_pk>/partes/nueva/', views.ParteCreateView.as_view(), name='parte_nueva'),
    path('partes/<int:pk>/editar/', views.ParteUpdateView.as_view(), name='parte_editar'),
    path('partes/<int:pk>/eliminar/', views.ParteDeleteView.as_view(), name='parte_eliminar'),

    path('expediente/<int:expediente_pk>/pasos/nuevo/', views.PasoCreateView.as_view(), name='paso_nuevo'),
    path('pasos/<int:pk>/editar/', views.PasoUpdateView.as_view(), name='paso_editar'),
    path('pasos/<int:pk>/eliminar/', views.PasoDeleteView.as_view(), name='paso_eliminar'),

    path('vencimientos/', views.VencimientoListView.as_view(), name='vencimientos'),
    path('expediente/<int:expediente_pk>/vencimientos/nuevo/', views.VencimientoCreateView.as_view(), name='vencimiento_nuevo'),
    path('vencimientos/<int:pk>/editar/', views.VencimientoUpdateView.as_view(), name='vencimiento_editar'),
    path('vencimientos/<int:pk>/eliminar/', views.VencimientoDeleteView.as_view(), name='vencimiento_eliminar'),
    path('vencimientos/<int:pk>/cumplir/', views.VencimientoCumplirView.as_view(), name='vencimiento_cumplir'),

    path('expediente/<int:expediente_pk>/honorarios/nuevo/', views.HonorarioCreateView.as_view(), name='honorario_nuevo'),
    path('honorarios/<int:pk>/editar/', views.HonorarioUpdateView.as_view(), name='honorario_editar'),
    path('honorarios/<int:pk>/eliminar/', views.HonorarioDeleteView.as_view(), name='honorario_eliminar'),

    path('expediente/<int:expediente_pk>/gastos/nuevo/', views.GastoCreateView.as_view(), name='gasto_nuevo'),
    path('gastos/<int:pk>/editar/', views.GastoUpdateView.as_view(), name='gasto_editar'),
    path('gastos/<int:pk>/eliminar/', views.GastoDeleteView.as_view(), name='gasto_eliminar'),

    # Adjuntos: la descarga pasa por una vista que verifica el dueño (no hay /media/ público).
    path('expediente/<int:expediente_pk>/adjuntos/nuevo/', views.AdjuntoCreateView.as_view(), name='adjunto_nuevo'),
    path('adjuntos/<int:pk>/eliminar/', views.AdjuntoDeleteView.as_view(), name='adjunto_eliminar'),
    path('adjuntos/<int:pk>/descargar/', views.AdjuntoDescargarView.as_view(), name='adjunto_descargar'),
]
