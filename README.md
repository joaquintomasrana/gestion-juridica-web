# Gestión Jurídica Web

Sistema web multiusuario para la gestión de expedientes de un estudio jurídico. Permite administrar causas, partes intervinientes, pasos procesales, vencimientos, honorarios, gastos y documentación adjunta, con acceso mediante usuario y contraseña y los datos almacenados de forma centralizada en la nube.

> Proyecto de práctica profesional — Teclab. **En desarrollo.**

## Descripción

La gestión de expedientes en un estudio jurídico suele resolverse con herramientas dispersas (planillas, carpetas de archivos, programas de escritorio en una sola máquina), lo que ata la información a un equipo, impide el trabajo de varias personas y no ofrece garantías sobre el resguardo de datos sensibles.

Este proyecto propone una aplicación web centralizada: un sistema accesible desde cualquier dispositivo con navegador, donde cada profesional inicia sesión y opera únicamente sobre sus expedientes, con la información persistida en una base de datos en la nube.

## Características

- Registro e inicio/cierre de sesión de usuarios.
- Gestión completa (alta, baja, modificación y consulta) de expedientes.
- Entidades asociadas a cada expediente: partes, pasos procesales, vencimientos, honorarios, gastos y archivos adjuntos.
- Listado de expedientes con búsqueda y filtros.
- Aislamiento de datos por usuario: cada uno accede solo a sus propios expedientes.
- Carga de archivos adjuntos.
- Persistencia en base de datos en la nube.

## Stack tecnológico

- **Lenguaje:** Python 3.12+
- **Framework:** Django 5.2 LTS
- **Base de datos:** SQLite (desarrollo) / PostgreSQL — Neon (producción)
- **Interfaz:** HTML + Pico.css
- **Servidor de producción:** Gunicorn
- **Archivos estáticos:** WhiteNoise
- **Despliegue:** Render

## Estado del proyecto

En desarrollo. Se trata de un proyecto académico y se utiliza **exclusivamente con datos ficticios de prueba**; no contiene ni está destinado a contener información real de clientes.

## Instalación y uso local

> La configuración se lee de variables de entorno. Es necesario un archivo `.env` (no versionado) con la clave `SECRET_KEY`. El archivo `.env.example` sirve de plantilla.

```bash
# Clonar el repositorio
git clone https://github.com/joaquintomasrana/gestion-juridica-web.git
cd gestion-juridica-web

# Crear y activar un entorno virtual
python -m venv .venv
# En Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# En Linux/Mac:
# source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Crear el archivo .env a partir de la plantilla
cp .env.example .env
# En Windows (PowerShell):
# Copy-Item .env.example .env

# Generar una clave secreta y pegarla en el .env como valor de SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Aplicar migraciones
python manage.py migrate

# Crear un usuario administrador
python manage.py createsuperuser

# Levantar el servidor de desarrollo
python manage.py runserver
```

Luego, abrir `http://127.0.0.1:8000/` en el navegador.

## Autor

Joaquín Raña
