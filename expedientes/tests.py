import os
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

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
