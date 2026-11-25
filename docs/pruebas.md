# Informe de pruebas — Gestión Jurídica Web

Este documento registra las pruebas realizadas sobre la aplicación antes de la entrega: qué se probó, cómo y qué demuestra cada resultado.

El sistema guarda información alcanzada por el secreto profesional. Por eso las pruebas ponen el foco en el **aislamiento de datos entre usuarios**: ningún usuario puede ver, modificar ni descargar información de otro.

## Entorno

| | |
|---|---|
| Fecha de ejecución | 25/11/2026 |
| Aplicación publicada | https://gestion-juridica.onrender.com |
| Servidor | Render (plan gratuito), Gunicorn, región Virginia (EE. UU.) |
| Base de datos | PostgreSQL en Neon (producción); SQLite (desarrollo y pruebas automáticas) |
| Python / Django | 3.13.17 / 5.2.17 |
| Datos | Exclusivamente ficticios, generados con `python manage.py cargar_demo`: usuarios `ana.demo` (12 expedientes) y `beto.demo` (4) |

## Resumen

| Tipo de prueba | Cantidad | Resultado |
|---|---|---|
| A. Pruebas automáticas (tests de Django) | 53 | ✅ 53 aprobadas |
| B. Pruebas de seguridad sobre la aplicación publicada | 14 | ✅ 14 aprobadas |
| C. Pruebas funcionales manuales (escritorio y celular) | 18 | ✅ 18 aprobadas |

---

## A. Pruebas automáticas

Se ejecutan con:

```
python manage.py test expedientes
```

Resultado: `Ran 53 tests ... OK`.

Cada prueba crea su propia base de datos temporal, que se descarta al terminar. Las pruebas de adjuntos usan además una carpeta temporal para los archivos.

La mayoría de las pruebas usa **dos usuarios**: Ana, que intenta acceder, y Beto, el dueño de los datos. Así se verifica que el sistema bloquee el acceso a información ajena.

### A.1 Detalle por grupo

| Grupo (clase) | Tests | Qué verifica |
|---|---|---|
| `AccesoSinSesionTests` | 1 | Sin sesión iniciada, las pantallas de expedientes redirigen al login |
| `AislamientoExpedientesTests` | 5 | El listado y la búsqueda muestran solo expedientes propios; ver, editar o eliminar uno ajeno responde 404 (por GET y por POST, sin modificar nada); el titular de un expediente nuevo lo asigna el servidor, aunque se intente enviar otro |
| `NumeroDeExpedienteTests` | 4 | Un número repetido para el mismo titular da un error de formulario (no un error del servidor); dos titulares pueden usar el mismo número; se admiten varios expedientes sin número; editar sin cambiar el número funciona |
| `MensajesTests` | 3 | Crear, editar y eliminar muestran un mensaje de confirmación |
| `EntidadesAsociadasTests` | 5 | Partes, pasos procesales, vencimientos, honorarios y gastos: se crean, editan y eliminan en expedientes propios; en expedientes ajenos responde 404; el expediente no se puede elegir desde el formulario |
| `VencimientoCumplirTests` | 3 | Marcar un vencimiento como cumplido funciona con uno propio, responde 404 con uno ajeno y rechaza GET (405) |
| `TotalesTests` | 1 | Los totales de honorarios se calculan por separado para cada moneda (pesos y dólares) |
| `PanelVencimientosTests` | 8 | Reglas de "vencido" y "vence pronto"; el panel muestra solo vencimientos pendientes y propios, ordenados por fecha; no hace una consulta por fila (problema N+1); después de "Cumplido" vuelve al panel sin aceptar redirecciones a sitios externos; exige sesión |
| `EstiloTests` | 2 | La página 404 es la propia de la aplicación y no revela datos ajenos; las hojas de estilo y la tipografía existen y se enlazan; el tema claro está fijado |
| `FiltroEstadoTests` | 5 | Al entrar se muestran solo los expedientes activos; "Todos" muestra todos los estados, sin incluir expedientes ajenos; el filtro por un estado y la búsqueda respetan la selección |
| `ObservacionesPasoTests` | 4 | Las observaciones de los pasos procesales se muestran en el detalle, respetando los saltos de línea; un texto con código HTML se muestra como texto y no se ejecuta; sin observaciones no aparece el desplegable; el recuadro de carga es amplio |
| `EstadoVencimientosDetalleTests` | 1 | Cada vencimiento muestra una sola etiqueta de estado: cumplido, vencido, próximo o pendiente |
| `AdjuntosTests` | 11 | Carga en expediente propio; rechazo de extensiones no permitidas y de archivos de más de 5 MB; rechazo de carga en expediente ajeno; el archivo se borra del disco al eliminar el adjunto o el expediente; un adjunto ajeno no se puede eliminar ni descargar; la descarga exige sesión; un archivo faltante responde 404; la carpeta `/media/` no es accesible públicamente |
| **Total** | **53** | |

### A.2 Validación de las pruebas (pruebas de mutación)

Una prueba que nunca falla no demuestra nada. Para comprobar que estas detectan errores reales, se **introdujeron fallas a propósito** en el código y se verificó que las pruebas fallaran. Después se restauró el código original.

| Falla introducida | Pruebas que fallaron |
|---|---|
| Quitar el filtro por dueño al editar o eliminar entidades asociadas | 10 |
| Quitar el control de dueño al crear entidades asociadas | 5 |
| Quitar el filtro por dueño al marcar un vencimiento como cumplido | 1 |
| Quitar el filtro por dueño en la descarga de adjuntos | 1 |
| Quitar el borrado del archivo del disco | 2 |
| Quitar la validación de tamaño de archivo | 1 |
| Quitar la validación de extensión de archivo | 1 |
| Quitar el manejo de archivo faltante | 1 |
| Quitar el filtro por dueño del panel de vencimientos | 1 |
| Quitar la optimización de consultas del panel (`select_related`) | 1 |
| Aceptar cualquier destino al volver desde "Cumplido" | 1 |

En todos los casos al menos una prueba detectó la falla.

---

## B. Pruebas de seguridad sobre la aplicación publicada

Se realizaron con pedidos HTTP (herramienta `curl`) a la URL pública. El objetivo fue verificar que la **configuración de producción** esté efectivamente activa en internet, algo que las pruebas automáticas, que corren en la computadora de desarrollo, no pueden comprobar.

| # | Prueba | Resultado esperado | Resultado obtenido |
|---|---|---|---|
| 1 | Acceso por `http://` | Redirección a `https://` | ✅ 301 → `https://...` |
| 2 | Encabezado HSTS | Presente | ✅ `strict-transport-security: max-age=3600` |
| 3 | Encabezados de seguridad | Presentes | ✅ `x-frame-options: DENY`, `x-content-type-options: nosniff`, `referrer-policy: same-origin`, `cross-origin-opener-policy: same-origin` |
| 4 | Cookie de sesión | Solo por HTTPS e inaccesible desde JavaScript | ✅ `Secure` y `HttpOnly` |
| 5 | Cookie CSRF | Solo por HTTPS | ✅ `Secure`, `SameSite=Lax` |
| 6 | Página inexistente | Página 404 propia, sin información de depuración | ✅ 404 propia; ningún rastro de la página de depuración de Django (confirma `DEBUG` desactivado) |
| 7 | Acceso directo a `/media/...` | Sin acceso | ✅ 404 |
| 8 | Listado, panel, detalle, alta y descarga de adjuntos sin sesión | Redirección al login | ✅ Las 5 rutas responden 302 → login |
| 9 | Panel de administración sin sesión | Redirección al login del admin | ✅ 302 → `/admin/login/` |
| 10 | Envío del login sin token CSRF | Rechazo | ✅ 403 |
| 11 | Cierre de sesión por GET | Rechazo (solo se acepta POST) | ✅ 405 |
| 12 | Pedido con un dominio falso en el encabezado `Host` | Rechazo | ✅ 403, rechazado por la plataforma antes de llegar a la aplicación; `ALLOWED_HOSTS` de Django actúa como segunda barrera |
| 13 | Archivos estáticos | Nombre con huella del contenido, comprimidos y con caché larga | ✅ `pico.min.94cbb1d0170a.css`, `gzip`, `max-age=315360000, immutable` |
| 14 | Inicio de sesión con usuario de demostración | Acceso a sus datos | ✅ Listado (200, 10 expedientes en la primera página) y panel de vencimientos (200) |

**Revisión de configuración (`python manage.py check --deploy`).** Con la configuración de producción quedan 2 advertencias, mantenidas de forma deliberada:

- **`W005`, HSTS en subdominios.** La aplicación usa un subdominio de un dominio ajeno (`onrender.com`); no corresponde extender la política a otros subdominios.
- **`W021`, HSTS *preload*.** Requiere dominio propio y es prácticamente irreversible. No aplica a una demostración.

---

## C. Pruebas funcionales manuales

Se recorrieron sobre la URL pública con un navegador de escritorio. La sección C.4 se realizó desde un celular con datos móviles, para verificar el acceso real desde internet y la adaptación a pantallas chicas.

### C.1 Cuentas

| Prueba | Resultado |
|---|---|
| Crear una cuenta nueva | ✅ |
| Iniciar sesión con contraseña incorrecta muestra un error claro | ✅ |
| Iniciar y cerrar sesión | ✅ |

### C.2 Funcionalidad (usuario `ana.demo`)

| Prueba | Resultado |
|---|---|
| El listado muestra los 12 expedientes, paginados de a 10 | ✅ |
| Búsqueda por texto y filtro por estado | ✅ |
| Crear un expediente; un número repetido muestra error | ✅ |
| Alta, edición y baja de partes, pasos, vencimientos, honorarios y gastos | ✅ |
| Marcar un vencimiento como cumplido | ✅ |
| Panel de vencimientos con vencidos y próximos diferenciados por color | ✅ |
| Subir, descargar y eliminar un archivo adjunto | ✅ |
| Rechazo de un tipo de archivo no permitido | ✅ |

### C.3 Aislamiento entre usuarios

| Prueba | Resultado |
|---|---|
| Con sesión de `beto.demo`, abrir la URL de un expediente de `ana.demo` | ✅ 404 ("No encontramos lo que buscás") |
| Con sesión de `beto.demo`, abrir la URL de descarga de un adjunto de `ana.demo` | ✅ 404 |
| Sin sesión, abrir esas mismas URLs | ✅ Redirección al login |

### C.4 Celular con datos móviles

| Prueba | Resultado |
|---|---|
| La aplicación carga desde internet | ✅ |
| Sin desplazamiento horizontal en listado, detalle y panel | ✅ |
| Formularios y botones utilizables en pantalla táctil | ✅ |

### C.5 Administración

| Prueba | Resultado |
|---|---|
| Ingreso al panel `/admin/` con el superusuario de producción | ✅ |

---

## Limitaciones conocidas

No son fallas de las pruebas. Son restricciones del entorno de despliegue gratuito, aceptadas para la demostración:

1. **Inactividad.** El servidor y la base de datos se suspenden tras un período sin uso. La primera visita posterior demora cerca de un minuto.
2. **Archivos adjuntos no persistentes.** El disco del servidor es efímero: los adjuntos se pierden en cada redespliegue o reinicio. Para un uso real se recomienda un almacenamiento de objetos externo (por ejemplo, Cloudflare R2 o Amazon S3); la vista de descarga protegida no requeriría cambios.
3. **Credenciales de demostración públicas.** Los usuarios de demostración tienen una contraseña conocida. Sus datos son ficticios y se restauran ejecutando nuevamente `cargar_demo`.

## Conclusión

La aplicación aprobó las 85 pruebas realizadas.

- **Aislamiento entre usuarios:** se verificó en tres niveles: pruebas automáticas, pruebas sobre la aplicación publicada y recorrido manual. Ningún usuario puede ver, modificar ni descargar información de otro.
- **Configuración de producción:** HTTPS obligatorio, cookies seguras, `DEBUG` desactivado y protección CSRF están efectivamente activos en el servidor publicado.
