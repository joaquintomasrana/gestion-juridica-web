import os
import shutil
import tempfile
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from .forms import TAMANIO_MAXIMO
from .models import ArchivoAdjunto, Expediente, Gasto, Honorario, Parte, PasoProcesal, Vencimiento

User = get_user_model()

# Para cada entidad: modelo, nombres de URL (alta, edición, eliminación) y datos válidos.
ENTIDADES = [
    (Parte, "parte_nueva", "parte_editar", "parte_eliminar",
     {"nombre": "Juan Lopez", "tipo": "actor"}),
    (PasoProcesal, "paso_nuevo", "paso_editar", "paso_eliminar",
     {"fecha": "2026-11-01", "descripcion": "Traslado"}),
    (Vencimiento, "vencimiento_nuevo", "vencimiento_editar", "vencimiento_eliminar",
     {"fecha": "2026-11-20", "descripcion": "Contestar", "estado": "pendiente"}),
    (Honorario, "honorario_nuevo", "honorario_editar", "honorario_eliminar",
     {"fecha": "2026-11-01", "monto": "1000.00", "moneda": "ARS"}),
    (Gasto, "gasto_nuevo", "gasto_editar", "gasto_eliminar",
     {"fecha": "2026-11-01", "monto": "200.00", "moneda": "ARS", "descripcion": "Tasa"}),
]


class DosUsuariosTestCase(TestCase):
    """Base: dos usuarios, cada uno con un expediente."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", password="x")
        cls.beto = User.objects.create_user("beto", password="x")
        cls.exp_ana = Expediente.objects.create(
            owner=cls.ana, caratula="Gomez c/ Perez", numero="100/2026"
        )
        cls.exp_beto = Expediente.objects.create(
            owner=cls.beto, caratula="Lopez c/ Diaz", numero="200/2026"
        )


class AccesoSinSesionTests(DosUsuariosTestCase):
    def test_sin_sesion_redirige_al_login(self):
        urls = [
            reverse("expedientes:lista"),
            reverse("expedientes:nuevo"),
            reverse("expedientes:detalle", args=[self.exp_ana.pk]),
            reverse("expedientes:editar", args=[self.exp_ana.pk]),
            reverse("expedientes:eliminar", args=[self.exp_ana.pk]),
            reverse("expedientes:parte_nueva", args=[self.exp_ana.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(respuesta, f"{reverse('login')}?next={url}")


class AislamientoExpedientesTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_el_listado_solo_muestra_los_propios(self):
        respuesta = self.client.get(reverse("expedientes:lista"))
        self.assertContains(respuesta, "Gomez c/ Perez")
        self.assertNotContains(respuesta, "Lopez c/ Diaz")

    def test_la_busqueda_no_trae_expedientes_ajenos(self):
        respuesta = self.client.get(reverse("expedientes:lista"), {"q": "Lopez"})
        self.assertNotContains(respuesta, "Lopez c/ Diaz")

    def test_expediente_ajeno_responde_404(self):
        for nombre in ["detalle", "editar", "eliminar"]:
            with self.subTest(vista=nombre):
                url = reverse(f"expedientes:{nombre}", args=[self.exp_beto.pk])
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_post_ajeno_no_modifica_nada(self):
        for nombre in ["editar", "eliminar"]:
            with self.subTest(vista=nombre):
                url = reverse(f"expedientes:{nombre}", args=[self.exp_beto.pk])
                respuesta = self.client.post(url, {"caratula": "Hackeado", "estado": "activo"})
                self.assertEqual(respuesta.status_code, 404)
        # Si lo hubieran borrado, refresh_from_db también haría fallar el test.
        self.exp_beto.refresh_from_db()
        self.assertEqual(self.exp_beto.caratula, "Lopez c/ Diaz")

    def test_crear_asigna_el_usuario_logueado_como_titular(self):
        self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Nuevo c/ Otro",
            "estado": "activo",
            "owner": self.beto.pk,  # intento de asignárselo a otro usuario
        })
        nuevo = Expediente.objects.get(caratula="Nuevo c/ Otro")
        self.assertEqual(nuevo.owner, self.ana)


class NumeroDeExpedienteTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_numero_repetido_del_mismo_usuario_da_error_de_formulario(self):
        respuesta = self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Otro", "estado": "activo", "numero": "100/2026",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya tenés un expediente con ese número.")

    def test_dos_usuarios_pueden_tener_el_mismo_numero(self):
        self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Otro", "estado": "activo", "numero": "200/2026",
        })
        self.assertTrue(Expediente.objects.filter(owner=self.ana, numero="200/2026").exists())

    def test_se_permiten_varios_expedientes_sin_numero(self):
        for caratula in ["Sin numero 1", "Sin numero 2"]:
            self.client.post(reverse("expedientes:nuevo"), {"caratula": caratula, "estado": "activo"})
        self.assertEqual(Expediente.objects.filter(owner=self.ana, numero__isnull=True).count(), 2)

    def test_editar_sin_cambiar_el_numero_funciona(self):
        respuesta = self.client.post(reverse("expedientes:editar", args=[self.exp_ana.pk]), {
            "caratula": "Gomez c/ Perez (editado)", "estado": "activo", "numero": "100/2026",
        })
        self.assertRedirects(respuesta, self.exp_ana.get_absolute_url())

class MensajesTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_crear_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:nuevo"),
            {"caratula": "Nuevo", "estado": "activo"},
            follow=True,
        )
        self.assertContains(respuesta, "Expediente creado.")

    def test_editar_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:editar", args=[self.exp_ana.pk]),
            {"caratula": "Editado", "estado": "activo"},
            follow=True,
        )
        self.assertContains(respuesta, "Cambios guardados.")
        
    def test_eliminar_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:eliminar", args=[self.exp_ana.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Expediente eliminado.")


# --- Fase 7B: entidades asociadas --------------------------------------------

class EntidadesAsociadasTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_crear_en_un_expediente_propio(self):
        for modelo, nueva, _, _, datos in ENTIDADES:
            with self.subTest(entidad=modelo.__name__):
                url = reverse(f"expedientes:{nueva}", args=[self.exp_ana.pk])
                respuesta = self.client.post(url, datos)
                self.assertRedirects(respuesta, self.exp_ana.get_absolute_url())
                self.assertEqual(modelo.objects.filter(expediente=self.exp_ana).count(), 1)

    def test_no_puede_crear_en_un_expediente_ajeno(self):
        for modelo, nueva, _, _, datos in ENTIDADES:
            with self.subTest(entidad=modelo.__name__):
                url = reverse(f"expedientes:{nueva}", args=[self.exp_beto.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, datos).status_code, 404)
                self.assertFalse(modelo.objects.filter(expediente=self.exp_beto).exists())

    def test_el_expediente_no_se_puede_elegir_desde_el_formulario(self):
        for modelo, nueva, _, _, datos in ENTIDADES:
            with self.subTest(entidad=modelo.__name__):
                url = reverse(f"expedientes:{nueva}", args=[self.exp_ana.pk])
                self.client.post(url, {**datos, "expediente": self.exp_beto.pk})
                self.assertFalse(modelo.objects.filter(expediente=self.exp_beto).exists())

    def test_no_puede_editar_ni_eliminar_entidades_ajenas(self):
        for modelo, _, editar, eliminar, datos in ENTIDADES:
            ajena = modelo.objects.create(expediente=self.exp_beto, **datos)
            for nombre in [editar, eliminar]:
                with self.subTest(entidad=modelo.__name__, vista=nombre):
                    url = reverse(f"expedientes:{nombre}", args=[ajena.pk])
                    self.assertEqual(self.client.get(url).status_code, 404)
                    self.assertEqual(self.client.post(url, datos).status_code, 404)
            self.assertTrue(modelo.objects.filter(pk=ajena.pk).exists())

    def test_editar_y_eliminar_entidades_propias(self):
        for modelo, _, editar, eliminar, datos in ENTIDADES:
            with self.subTest(entidad=modelo.__name__):
                propia = modelo.objects.create(expediente=self.exp_ana, **datos)
                url = reverse(f"expedientes:{editar}", args=[propia.pk])
                self.assertRedirects(self.client.post(url, datos), self.exp_ana.get_absolute_url())
                url = reverse(f"expedientes:{eliminar}", args=[propia.pk])
                self.assertRedirects(self.client.post(url), self.exp_ana.get_absolute_url())
                self.assertFalse(modelo.objects.filter(pk=propia.pk).exists())


class VencimientoCumplirTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def crear(self, expediente):
        return Vencimiento.objects.create(
            expediente=expediente, fecha="2026-11-20", descripcion="Contestar"
        )

    def test_marcar_cumplido_un_vencimiento_propio(self):
        vencimiento = self.crear(self.exp_ana)
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        self.assertRedirects(self.client.post(url), self.exp_ana.get_absolute_url())
        vencimiento.refresh_from_db()
        self.assertEqual(vencimiento.estado, Vencimiento.Estado.CUMPLIDO)

    def test_no_puede_marcar_cumplido_un_vencimiento_ajeno(self):
        vencimiento = self.crear(self.exp_beto)
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        vencimiento.refresh_from_db()
        self.assertEqual(vencimiento.estado, Vencimiento.Estado.PENDIENTE)

    def test_marcar_cumplido_solo_acepta_post(self):
        vencimiento = self.crear(self.exp_ana)
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        self.assertEqual(self.client.get(url).status_code, 405)


class TotalesTests(DosUsuariosTestCase):
    def test_los_totales_se_separan_por_moneda(self):
        for monto, moneda in [("1000.00", "ARS"), ("500.00", "ARS"), ("300.00", "USD")]:
            Honorario.objects.create(expediente=self.exp_ana, fecha="2026-11-01", monto=monto, moneda=moneda)
        self.client.force_login(self.ana)
        respuesta = self.client.get(self.exp_ana.get_absolute_url())
        self.assertEqual(list(respuesta.context["totales_honorarios"]), [
            {"moneda": "ARS", "total": Decimal("1500.00")},
            {"moneda": "USD", "total": Decimal("300.00")},
        ])


# --- Fase 9B: panel de vencimientos --------------------------------------------

class PanelVencimientosTests(DosUsuariosTestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.client.force_login(self.ana)

    def crear(self, expediente, dias, descripcion, estado=Vencimiento.Estado.PENDIENTE):
        return Vencimiento.objects.create(
            expediente=expediente, fecha=self.hoy + timedelta(days=dias),
            descripcion=descripcion, estado=estado,
        )

    def test_esta_vencido_y_vence_pronto(self):
        P, C = Vencimiento.Estado.PENDIENTE, Vencimiento.Estado.CUMPLIDO
        # (días desde hoy, estado, esta_vencido esperado, vence_pronto esperado)
        casos = [
            (-1, P, True, False),
            (0, P, False, True),
            (7, P, False, True),
            (8, P, False, False),
            (-1, C, False, False),
            (3, C, False, False),
        ]
        for dias, estado, vencido, pronto in casos:
            with self.subTest(dias=dias, estado=estado):
                v = Vencimiento(expediente=self.exp_ana, fecha=self.hoy + timedelta(days=dias), estado=estado)
                self.assertEqual(v.esta_vencido, vencido)
                self.assertEqual(v.vence_pronto, pronto)

    def test_el_panel_solo_muestra_vencimientos_propios(self):
        self.crear(self.exp_ana, 0, "Contestar demanda")
        self.crear(self.exp_beto, 0, "Apelar sentencia")
        respuesta = self.client.get(reverse("expedientes:vencimientos"))
        self.assertContains(respuesta, "Contestar demanda")
        self.assertNotContains(respuesta, "Apelar sentencia")
        self.assertNotContains(respuesta, "Lopez c/ Diaz")

    def test_el_panel_no_muestra_los_cumplidos(self):
        self.crear(self.exp_ana, 2, "Ya presentado", estado=Vencimiento.Estado.CUMPLIDO)
        respuesta = self.client.get(reverse("expedientes:vencimientos"))
        self.assertNotContains(respuesta, "Ya presentado")
        self.assertContains(respuesta, "No tenés vencimientos pendientes.")

    def test_el_panel_ordena_por_fecha_y_marca_vencidos_y_proximos(self):
        self.crear(self.exp_ana, 30, "Lejano")
        self.crear(self.exp_ana, -5, "Atrasado")
        self.crear(self.exp_ana, 3, "Cercano")
        respuesta = self.client.get(reverse("expedientes:vencimientos"))
        self.assertEqual(
            [v.descripcion for v in respuesta.context["vencimientos"]],
            ["Atrasado", "Cercano", "Lejano"],
        )
        self.assertEqual(respuesta.context["cantidad_vencidos"], 1)
        self.assertEqual(respuesta.context["cantidad_proximos"], 1)

    def test_el_panel_no_hace_una_consulta_por_fila(self):
        """Problema N+1: con select_related, más filas no implican más consultas."""
        url = reverse("expedientes:vencimientos")
        self.crear(self.exp_ana, 1, "Uno")
        with CaptureQueriesContext(connection) as con_una:
            self.client.get(url)
        for i in range(5):
            self.crear(self.exp_ana, i, f"Otro {i}")
        with CaptureQueriesContext(connection) as con_seis:
            self.client.get(url)
        self.assertEqual(len(con_una), len(con_seis))

    def test_cumplir_desde_el_panel_vuelve_al_panel(self):
        vencimiento = self.crear(self.exp_ana, 1, "Contestar")
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        respuesta = self.client.post(url, {"volver": "panel"})
        self.assertRedirects(respuesta, reverse("expedientes:vencimientos"))

    def test_volver_no_acepta_urls_externas(self):
        vencimiento = self.crear(self.exp_ana, 1, "Contestar")
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        respuesta = self.client.post(url, {"volver": "https://sitio-malicioso.example"})
        self.assertRedirects(respuesta, self.exp_ana.get_absolute_url())

    def test_sin_sesion_redirige_al_login(self):
        self.client.logout()
        url = reverse("expedientes:vencimientos")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")


# --- Fase 9: estilo y páginas de error -----------------------------------------

class EstiloTests(DosUsuariosTestCase):
    def test_la_pagina_404_es_la_propia(self):
        # Los tests corren con DEBUG=False, así que se usa templates/404.html.
        self.client.force_login(self.ana)
        respuesta = self.client.get(reverse("expedientes:detalle", args=[self.exp_beto.pk]))
        self.assertContains(respuesta, "No encontramos lo que buscás", status_code=404)
        self.assertNotContains(respuesta, "Lopez c/ Diaz", status_code=404)

    def test_los_estilos_existen_y_se_enlazan(self):
        rutas = [
            "expedientes/pico.min.css",
            "expedientes/estilos.css",
            "expedientes/fuentes/ibm-plex-sans-latin-wght.woff2",
        ]
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                self.assertIsNotNone(finders.find(ruta))
        respuesta = self.client.get(reverse("login"))
        self.assertContains(respuesta, "pico.min.css")
        self.assertContains(respuesta, 'name="viewport"')
        # Tema claro fijo: la paleta no debe mezclarse con el modo oscuro de Pico.
        self.assertContains(respuesta, 'data-theme="light"')


# --- Cambios posteriores: filtro de activos y observaciones de los pasos ------

class FiltroEstadoTests(DosUsuariosTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()  # exp_ana ("Gomez c/ Perez") queda activo
        Expediente.objects.create(
            owner=cls.ana, caratula="Ruiz c/ Sosa", estado=Expediente.Estado.ARCHIVADO
        )
        Expediente.objects.create(
            owner=cls.ana, caratula="Vera c/ Paz", estado=Expediente.Estado.CERRADO
        )

    def setUp(self):
        self.client.force_login(self.ana)

    def ver(self, **parametros):
        return self.client.get(reverse("expedientes:lista"), parametros)

    def test_al_entrar_muestra_solo_los_activos(self):
        respuesta = self.ver()
        self.assertContains(respuesta, "Gomez c/ Perez")
        self.assertNotContains(respuesta, "Ruiz c/ Sosa")
        self.assertNotContains(respuesta, "Vera c/ Paz")

    def test_todos_muestra_todos_los_estados(self):
        respuesta = self.ver(estado="todos")
        for caratula in ["Gomez c/ Perez", "Ruiz c/ Sosa", "Vera c/ Paz"]:
            with self.subTest(caratula=caratula):
                self.assertContains(respuesta, caratula)

    def test_filtrar_por_un_estado(self):
        respuesta = self.ver(estado="archivado")
        self.assertContains(respuesta, "Ruiz c/ Sosa")
        self.assertNotContains(respuesta, "Gomez c/ Perez")

    def test_la_busqueda_respeta_el_filtro_por_defecto(self):
        self.assertNotContains(self.ver(q="Ruiz"), "Ruiz c/ Sosa")
        self.assertContains(self.ver(q="Ruiz", estado="todos"), "Ruiz c/ Sosa")

    def test_todos_sigue_sin_mostrar_expedientes_ajenos(self):
        self.assertNotContains(self.ver(estado="todos"), "Lopez c/ Diaz")


class InicioTests(DosUsuariosTestCase):
    """Dashboard de la pantalla inicial."""

    def setUp(self):
        self.hoy = timezone.localdate()
        self.client.force_login(self.ana)

    def vencimiento(self, expediente, dias, descripcion, estado=Vencimiento.Estado.PENDIENTE):
        return Vencimiento.objects.create(
            expediente=expediente, fecha=self.hoy + timedelta(days=dias),
            descripcion=descripcion, estado=estado,
        )

    def ver(self):
        return self.client.get(reverse("expedientes:inicio"))

    def test_es_la_pantalla_inicial_y_exige_sesion(self):
        self.assertEqual(reverse("expedientes:inicio"), "/")
        self.client.logout()
        self.assertRedirects(self.ver(), f"{reverse('login')}?next=/")

    def test_al_iniciar_sesion_se_llega_al_dashboard(self):
        self.client.logout()
        self.ana.set_password("clave-segura-123")
        self.ana.save()
        respuesta = self.client.post(reverse("login"), {"username": "ana", "password": "clave-segura-123"})
        self.assertRedirects(respuesta, reverse("expedientes:inicio"))

    def test_cuenta_los_expedientes_en_tramite(self):
        Expediente.objects.create(owner=self.ana, caratula="Archivado", estado=Expediente.Estado.ARCHIVADO)
        self.assertEqual(self.ver().context["en_tramite"], 1)  # exp_ana; el archivado y el de Beto no

    def test_vencimientos_de_hoy_y_de_los_proximos_7_dias(self):
        self.vencimiento(self.exp_ana, 0, "Hoy")
        self.vencimiento(self.exp_ana, 1, "Manana")
        self.vencimiento(self.exp_ana, 7, "En siete dias")
        self.vencimiento(self.exp_ana, 8, "En ocho dias")
        self.vencimiento(self.exp_ana, 0, "Hoy pero cumplido", estado=Vencimiento.Estado.CUMPLIDO)
        contexto = self.ver().context
        self.assertEqual([v.descripcion for v in contexto["vencen_hoy"]], ["Hoy"])
        self.assertEqual([v.descripcion for v in contexto["proximos"]], ["Manana", "En siete dias"])

    def test_avisa_si_hay_vencimientos_sin_resolver(self):
        self.assertNotContains(self.ver(), "sin resolver")
        self.vencimiento(self.exp_ana, -3, "Atrasado")
        self.vencimiento(self.exp_ana, -10, "Cumplido a tiempo", estado=Vencimiento.Estado.CUMPLIDO)
        respuesta = self.ver()
        self.assertEqual(respuesta.context["cantidad_vencidos"], 1)
        self.assertContains(respuesta, "tenés 1 vencimiento sin resolver")

    def test_cuenta_los_expedientes_con_movimiento_en_el_ultimo_mes(self):
        hace_40_dias = timezone.now() - timedelta(days=40)
        viejo = Expediente.objects.create(owner=self.ana, caratula="Sin movimiento")
        Expediente.objects.filter(pk=viejo.pk).update(actualizado=hace_40_dias)
        self.assertEqual(self.ver().context["con_movimiento"], 1)  # solo exp_ana

    def test_no_incluye_datos_de_otros_usuarios(self):
        self.vencimiento(self.exp_beto, 0, "Vence hoy de Beto")
        self.vencimiento(self.exp_beto, -2, "Vencido de Beto")
        respuesta = self.ver()
        contexto = respuesta.context
        self.assertEqual(contexto["vencen_hoy"], [])
        self.assertEqual(contexto["cantidad_vencidos"], 0)
        self.assertEqual(contexto["en_tramite"], 1)
        self.assertEqual(contexto["con_movimiento"], 1)
        self.assertNotContains(respuesta, "de Beto")

    def test_cada_tarjeta_dice_que_cuenta(self):
        # Un número suelto confunde: cada tarjeta nombra si son expedientes o vencimientos.
        self.vencimiento(self.exp_ana, 2, "Contestar")
        respuesta = self.ver()
        for texto in [
            "Expediente en trámite",
            "Vencimientos hoy",
            "Vencimiento en los próximos 7 días",
            "Expediente con movimiento en los últimos 30 días",
        ]:
            with self.subTest(texto=texto):
                self.assertContains(respuesta, texto)

    def test_cumplido_desde_el_dashboard_vuelve_al_dashboard(self):
        vencimiento = self.vencimiento(self.exp_ana, 0, "Hoy")
        url = reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk])
        self.assertRedirects(self.client.post(url, {"volver": "inicio"}), reverse("expedientes:inicio"))


class UltimaActualizacionTests(DosUsuariosTestCase):
    """Bug: la "última actualización" del expediente quedaba igual a su creación.

    Cualquier cambio en el expediente o en sus datos asociados (partes, pasos,
    vencimientos, honorarios, gastos, adjuntos) cuenta como actividad sobre él.
    """

    # Mediodía UTC: en la hora de Argentina sigue siendo el 01/01/2020
    # (a medianoche UTC sería el 31/12/2019 y el test del listado no probaría nada).
    FECHA_VIEJA = datetime(2020, 1, 1, 15, 0, tzinfo=dt_timezone.utc)

    def setUp(self):
        self.client.force_login(self.ana)
        # Se lleva la fecha a 2020 para detectar si la acción la actualiza.
        Expediente.objects.filter(pk=self.exp_ana.pk).update(
            creado=self.FECHA_VIEJA, actualizado=self.FECHA_VIEJA
        )

    def assert_actualizado(self):
        self.exp_ana.refresh_from_db()
        self.assertGreater(self.exp_ana.actualizado, self.FECHA_VIEJA)
        self.assertEqual(self.exp_ana.creado, self.FECHA_VIEJA)  # la creación no cambia

    def reiniciar(self):
        Expediente.objects.filter(pk=self.exp_ana.pk).update(actualizado=self.FECHA_VIEJA)

    def test_editar_el_expediente(self):
        self.client.post(reverse("expedientes:editar", args=[self.exp_ana.pk]),
                         {"caratula": "Gomez c/ Perez", "estado": "activo"})
        self.assert_actualizado()

    def test_crear_editar_y_eliminar_entidades_asociadas(self):
        for modelo, nueva, editar, eliminar, datos in ENTIDADES:
            with self.subTest(entidad=modelo.__name__, accion="crear"):
                self.client.post(reverse(f"expedientes:{nueva}", args=[self.exp_ana.pk]), datos)
                self.assert_actualizado()
            entidad = modelo.objects.get(expediente=self.exp_ana)
            with self.subTest(entidad=modelo.__name__, accion="editar"):
                self.reiniciar()
                self.client.post(reverse(f"expedientes:{editar}", args=[entidad.pk]), datos)
                self.assert_actualizado()
            with self.subTest(entidad=modelo.__name__, accion="eliminar"):
                self.reiniciar()
                self.client.post(reverse(f"expedientes:{eliminar}", args=[entidad.pk]))
                self.assert_actualizado()
            self.reiniciar()

    def test_marcar_un_vencimiento_como_cumplido(self):
        vencimiento = Vencimiento.objects.create(
            expediente=self.exp_ana, fecha="2026-11-20", descripcion="Contestar"
        )
        self.reiniciar()
        self.client.post(reverse("expedientes:vencimiento_cumplir", args=[vencimiento.pk]))
        self.assert_actualizado()

    def test_un_cambio_ajeno_no_toca_otros_expedientes(self):
        exp_beto_antes = Expediente.objects.get(pk=self.exp_beto.pk).actualizado
        self.client.post(reverse("expedientes:parte_nueva", args=[self.exp_ana.pk]),
                         {"nombre": "Juan Lopez", "tipo": "actor"})
        self.assertEqual(Expediente.objects.get(pk=self.exp_beto.pk).actualizado, exp_beto_antes)

    def test_el_listado_muestra_primero_el_de_actividad_mas_reciente(self):
        # El más antiguo (creado primero) pasa arriba al recibir un paso nuevo.
        nuevo = Expediente.objects.create(owner=self.ana, caratula="Nuevo c/ Reciente")
        respuesta = self.client.get(reverse("expedientes:lista"))
        self.assertEqual(respuesta.context["expedientes"][0], nuevo)

        self.client.post(reverse("expedientes:paso_nuevo", args=[self.exp_ana.pk]),
                         {"fecha": "2026-11-01", "descripcion": "Traslado"})
        respuesta = self.client.get(reverse("expedientes:lista"))
        self.assertEqual(respuesta.context["expedientes"][0], self.exp_ana)

    def test_el_listado_muestra_la_ultima_actualizacion(self):
        self.client.post(reverse("expedientes:parte_nueva", args=[self.exp_ana.pk]),
                         {"nombre": "Juan Lopez", "tipo": "actor"})
        respuesta = self.client.get(reverse("expedientes:lista"))
        self.assertNotContains(respuesta, "01/01/2020")


class EstadoVencimientosDetalleTests(DosUsuariosTestCase):
    def test_cada_vencimiento_muestra_su_estado_con_su_color(self):
        hoy = timezone.localdate()
        casos = [
            # (días desde hoy, estado guardado, clase CSS esperada)
            (-3, Vencimiento.Estado.CUMPLIDO, "cumplido"),
            (-3, Vencimiento.Estado.PENDIENTE, "vencido"),
            (2, Vencimiento.Estado.PENDIENTE, "proximo"),
            (30, Vencimiento.Estado.PENDIENTE, "pendiente"),
        ]
        self.client.force_login(self.ana)
        for dias, estado, clase in casos:
            with self.subTest(clase=clase):
                Vencimiento.objects.all().delete()
                Vencimiento.objects.create(
                    expediente=self.exp_ana, fecha=hoy + timedelta(days=dias),
                    descripcion="Plazo", estado=estado,
                )
                respuesta = self.client.get(self.exp_ana.get_absolute_url())
                self.assertContains(respuesta, f'<span class="{clase}">')
                # Una sola etiqueta: un cumplido nunca aparece además como "Vencido".
                otras = {"cumplido", "vencido", "proximo", "pendiente"} - {clase}
                for otra in otras:
                    self.assertNotContains(respuesta, f'<span class="{otra}">')


class ObservacionesPasoTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_el_detalle_muestra_las_observaciones_de_los_pasos(self):
        PasoProcesal.objects.create(
            expediente=self.exp_ana, fecha="2026-11-01", descripcion="Demanda",
            observaciones="Primer párrafo del escrito.\nSegundo párrafo.",
        )
        respuesta = self.client.get(self.exp_ana.get_absolute_url())
        self.assertContains(respuesta, "Ver observaciones")
        self.assertContains(respuesta, "Primer párrafo del escrito.\nSegundo párrafo.")

    def test_las_observaciones_no_ejecutan_html(self):
        # Un escrito pegado con etiquetas HTML se muestra como texto, nunca se ejecuta.
        PasoProcesal.objects.create(
            expediente=self.exp_ana, fecha="2026-11-01", descripcion="Prueba",
            observaciones="<script>alert('x')</script>",
        )
        respuesta = self.client.get(self.exp_ana.get_absolute_url())
        self.assertNotContains(respuesta, "<script>alert")
        self.assertContains(respuesta, "&lt;script&gt;")

    def test_sin_observaciones_no_aparece_el_desplegable(self):
        PasoProcesal.objects.create(expediente=self.exp_ana, fecha="2026-11-01", descripcion="Traslado")
        self.assertNotContains(self.client.get(self.exp_ana.get_absolute_url()), "Ver observaciones")

    def test_el_recuadro_de_observaciones_es_amplio(self):
        respuesta = self.client.get(reverse("expedientes:paso_nuevo", args=[self.exp_ana.pk]))
        self.assertContains(respuesta, 'rows="15"')


# --- Fase 8A / 8B: archivos adjuntos ------------------------------------------

MEDIA_DE_PRUEBA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA_DE_PRUEBA)
class AdjuntosTests(DosUsuariosTestCase):
    """Usa una carpeta temporal para no ensuciar media/ con archivos de prueba."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_DE_PRUEBA, ignore_errors=True)
        super().tearDownClass()

    def subir(self, expediente, nombre="escrito.pdf", contenido=b"contenido de prueba"):
        archivo = SimpleUploadedFile(nombre, contenido)
        url = reverse("expedientes:adjunto_nuevo", args=[expediente.pk])
        return self.client.post(url, {"archivo": archivo, "descripcion": "Escrito"})

    def subir_como_beto(self):
        """Deja un adjunto en el expediente de Beto y vuelve a loguear a Ana."""
        self.client.force_login(self.beto)
        self.subir(self.exp_beto)
        self.client.force_login(self.ana)
        return self.exp_beto.adjuntos.get()

    # --- 8A: carga y eliminación ---

    def test_subir_un_adjunto_propio(self):
        self.client.force_login(self.ana)
        self.assertRedirects(self.subir(self.exp_ana), self.exp_ana.get_absolute_url())
        adjunto = self.exp_ana.adjuntos.get()
        self.assertTrue(os.path.exists(adjunto.archivo.path))

    def test_rechaza_extensiones_no_permitidas(self):
        self.client.force_login(self.ana)
        respuesta = self.subir(self.exp_ana, nombre="virus.exe")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "extensión")
        self.assertFalse(ArchivoAdjunto.objects.exists())

    def test_rechaza_archivos_de_mas_de_5_mb(self):
        self.client.force_login(self.ana)
        respuesta = self.subir(self.exp_ana, contenido=b"x" * (TAMANIO_MAXIMO + 1))
        self.assertContains(respuesta, "El archivo supera el máximo de 5 MB.")
        self.assertFalse(ArchivoAdjunto.objects.exists())

    def test_no_puede_subir_a_un_expediente_ajeno(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.subir(self.exp_beto).status_code, 404)
        self.assertFalse(ArchivoAdjunto.objects.exists())

    def test_eliminar_el_adjunto_borra_el_archivo_del_disco(self):
        self.client.force_login(self.ana)
        self.subir(self.exp_ana)
        adjunto = self.exp_ana.adjuntos.get()
        ruta = adjunto.archivo.path
        url = reverse("expedientes:adjunto_eliminar", args=[adjunto.pk])
        self.assertRedirects(self.client.post(url), self.exp_ana.get_absolute_url())
        self.assertFalse(os.path.exists(ruta))

    def test_eliminar_el_expediente_borra_los_archivos_del_disco(self):
        self.client.force_login(self.ana)
        self.subir(self.exp_ana)
        ruta = self.exp_ana.adjuntos.get().archivo.path
        self.client.post(reverse("expedientes:eliminar", args=[self.exp_ana.pk]))
        self.assertFalse(os.path.exists(ruta))

    def test_subir_y_eliminar_un_adjunto_actualiza_el_expediente(self):
        viejo = datetime(2020, 1, 1, 15, 0, tzinfo=dt_timezone.utc)
        self.client.force_login(self.ana)
        Expediente.objects.filter(pk=self.exp_ana.pk).update(actualizado=viejo)
        self.subir(self.exp_ana)
        self.exp_ana.refresh_from_db()
        self.assertGreater(self.exp_ana.actualizado, viejo)

        Expediente.objects.filter(pk=self.exp_ana.pk).update(actualizado=viejo)
        adjunto = self.exp_ana.adjuntos.get()
        self.client.post(reverse("expedientes:adjunto_eliminar", args=[adjunto.pk]))
        self.exp_ana.refresh_from_db()
        self.assertGreater(self.exp_ana.actualizado, viejo)

    def test_no_puede_eliminar_un_adjunto_ajeno(self):
        adjunto = self.subir_como_beto()
        url = reverse("expedientes:adjunto_eliminar", args=[adjunto.pk])
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertTrue(os.path.exists(adjunto.archivo.path))

    # --- 8B: descarga protegida ---

    def test_descargar_un_adjunto_propio(self):
        self.client.force_login(self.ana)
        self.subir(self.exp_ana)
        adjunto = self.exp_ana.adjuntos.get()
        respuesta = self.client.get(reverse("expedientes:adjunto_descargar", args=[adjunto.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertEqual(b"".join(respuesta.streaming_content), b"contenido de prueba")

    def test_no_puede_descargar_un_adjunto_ajeno(self):
        adjunto = self.subir_como_beto()
        url = reverse("expedientes:adjunto_descargar", args=[adjunto.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.logout()
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_archivo_faltante_en_disco_responde_404(self):
        self.client.force_login(self.ana)
        self.subir(self.exp_ana)
        adjunto = self.exp_ana.adjuntos.get()
        os.remove(adjunto.archivo.path)  # simula el disco efímero de Render
        url = reverse("expedientes:adjunto_descargar", args=[adjunto.pk])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_media_no_es_publico(self):
        self.client.force_login(self.ana)
        self.subir(self.exp_ana)
        adjunto = self.exp_ana.adjuntos.get()
        self.assertEqual(self.client.get(f"/media/{adjunto.archivo.name}").status_code, 404)
