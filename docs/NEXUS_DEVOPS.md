# NEXUS: preparar los artefactos para Nexus

---

Procedimiento local en PowerShell. Genera los archivos de `dist/`; no los publica.
Requisitos: Python 3.13, uv y Git disponibles en `PATH`.

## Variables de entorno del flujo Nexus

La construcción local de la CLI y la plantilla **no requiere variables propias
de Nexus ni credenciales**. Este procedimiento deja la publicación a cargo del
equipo responsable; no ejecuta uploads ni configura sesiones del navegador.

### Definir los directorios en Nexus antes de distribuir la CLI

**EL DIRECTORIO DE DISTRIBUCIÓN DE LA HERRAMIENTA DEBE LLAMARSE `cli` Y DEBE
CREARSE SÍ O SÍ EN ESTE PROCEDIMIENTO.** Mantener el nombre en minúsculas: los
enlaces de descarga documentados usan `cli/<versión-cli>/`. Esta es una convención
de distribución; la CLI instalada no descarga ni valida su propio wheel.

El directorio de plantillas puede llamarse `python-service-archetype` u otro nombre acordado
con Arquitectura. Su ruta relativa debe coincidir exactamente, incluidas las
mayúsculas/minúsculas, con `ARCHETYPE_NEXUS_TEMPLATE_PATH` en la **sesión del developer.**
Cambiarla no cambia la identidad interna del arquetipo, el nombre del servicio
generado ni la salida local `dist/python-service-archetype/`; cambia dónde se publican y buscan
el ZIP y su checksum. Actualizar también las rutas de publicación y las instrucciones
entregadas a los developers.

Estructura remota de referencia; las versiones de CLI y plantilla son independientes:

```text
python-archetypes/                    # Repositorio Raw hosted
├── cli/                             # Nombre obligatorio en este procedimiento
│   └── <versión-cli>/
│       ├── institutional_python_cli-<versión-cli>-py3-none-any.whl
│       └── institutional_python_cli-<versión-cli>.tar.gz
└── python-service-archetype/                     # Nombre configurable
    └── <versión-plantilla>/
        ├── archetype.zip
        └── archetype.zip.sha256
```

En Nexus Raw no hace falta crear carpetas vacías: se materializan al subir los
archivos con el directorio de destino indicado. Primero acordar esta estructura;
después construir y verificar los artefactos con los pasos 1 a 5. La sección
**[Entrega para publicación](#entrega-para-publicación)** explica cómo cargar cada grupo y crear sus rutas.

Las siguientes variables las consume `create-python-project` cuando el developer
descarga una plantilla para crear su servicio:

| Variable | Propósito | Requisito / valor predeterminado |
|---|---|---|
| `ARCHETYPE_NEXUS_URL` | Base del repositorio Raw, por ejemplo `https://nexus.example.com/repository/python-archetypes/`. No incluir subdirectorios, versión ni nombre de archivo. | Opcional; la CLI usa `http://localhost:8082/repository/python-archetypes/` si no se define. `--nexus-url` tiene prioridad. |
| `ARCHETYPE_NEXUS_TEMPLATE_PATH` | Directorio remoto relativo que contiene las versiones de plantilla, por ejemplo `python-service-archetype` o `arquetipos/python`. | Obligatorio para descargar desde Nexus; no tiene valor predeterminado. No se exige con `--archive`. |
| `NEXUS_USERNAME` | Usuario para consultar assets y descargar ZIP/SHA-256. | Configurarlo junto con `NEXUS_TOKEN` si Nexus requiere autenticación. Solo lectura y listado para el consumo; no permisos de publicación. |
| `NEXUS_TOKEN` | Token o password para autenticación Basic. | Configurarlo junto con `NEXUS_USERNAME`. Sin ambos, la CLI intenta acceso anónimo; nunca incluir secretos en artefactos o Git. |

Las credenciales de Nexus deben configurarse como **variables de entorno en PowerShell**, no en `.env`, ya que la CLI no carga este archivo. El README principal incluye instrucciones para su captura segura y eliminación.

**Consideraciones:**
- Las credenciales no autentican automáticamente la descarga del wheel mediante navegador ni su instalación con `uv`.
- El uso de un ZIP local mediante `--archive` no requiere credenciales de Nexus.

#### Validación y generación de proyectos

- **Integridad:** todo ZIP local debe incluir su archivo `.zip.sha256`. No se aceptan hashes proporcionados únicamente por consola.
- **Dependencias:** la CLI valida exclusivamente con `uv` y permite acceso a red para instalar dependencias.
- **Git:** es obligatorio contar con Git e identidad configurada para generar el commit inicial en la rama `main`.

Estas condiciones aplican tanto para plantillas locales (`--archive`) como para las descargadas desde Nexus.

#### Publicación en Nexus

Se utiliza la siguiente estructura de directorios:

- **CLI:** `cli/<versión-cli>/`
- **Arquetipo:** `python-service-archetype/<versión-plantilla>/` (ZIP y SHA-256).

Si cambia la ruta remota del arquetipo, se debe comunicar a los desarrolladores para configurar `ARCHETYPE_NEXUS_TEMPLATE_PATH` con el nuevo valor.

**Importante:** este cambio no modifica la identidad del arquetipo ni la ruta local de generación `dist/python-service-archetype/`.

```powershell
$env:ARCHETYPE_NEXUS_TEMPLATE_PATH = "python-service-archetype"
```

Si el directorio acordado es `arquetipos/python`, usar ese valor literal en lugar
de `python-service-archetype`; no escribir textos explicativos ni incluir la versión en la variable.

La ruta admite hasta 512 caracteres, con segmentos de letras ASCII, números,
puntos, guiones y guiones bajos separados por `/`. No admite URLs, espacios,
escapes, barras al inicio/final, segmentos vacíos, `.` ni `..`.
La CLI diferencia un error local de configuración (variable ausente o inválida)
de un error al consultar Nexus (HTTP, conexión o listado sin plantillas completas).
Una ruta válida no demuestra que existan artefactos: eso se comprueba al consultar
el servidor. La misma ruta se usa para descubrir versiones y descargar ZIP/SHA-256.

---
## 1. Abrir la raíz del proyecto

Ubicarse en `archetype-python-service-archetype`, donde están `pyproject.toml`, `scripts/`,
`src/` y `tools/`. No entrar en `tools/archetype_cli`.

## 2. Preparar y validar

```powershell
uv sync --locked
.\scripts\validate.ps1
```

Ejecutar cada comando solo si el anterior terminó correctamente. Si falla,
detener la preparación y corregir el error. No se requieren tokens de Nexus,
SonarQube ni NVD para esta validación local.

## 3. Construir la CLI

```powershell
uv lock --check --project tools/archetype_cli
uv build --project tools/archetype_cli --out-dir dist/cli
```

La versión actual en `tools/archetype_cli/pyproject.toml` es **0.1.1**:

```text
dist/cli/
├── institutional_python_cli-0.1.1-py3-none-any.whl
└── institutional_python_cli-0.1.1.tar.gz
```

- `.whl`: herramienta instalable para el developer.
- `.tar.gz`: distribución fuente de la misma herramienta.

El ejemplo previo con `0.1.0` corresponde a esa versión de la CLI, no al build
actual. No renombrar los archivos para simular otra versión. No usar solamente
`uv build`: construiría la aplicación principal, no específicamente la CLI.

## 4. Construir la plantilla

```powershell
uv run --locked python scripts/build_archetype.py --template-version 0.1.0
```

Produce la plantilla que Cookiecutter transforma en un microservicio y su
checksum SHA-256. Las versiones de CLI y plantilla son independientes, aunque
en este ejemplo ambas sean `0.1.0`.

## 5. Confirmar los archivos

```powershell
Get-ChildItem .\dist\cli
Get-ChildItem .\dist\python-service-archetype\0.1.0
Get-FileHash .\dist\python-service-archetype\0.1.0\archetype.zip -Algorithm SHA256
Get-Content .\dist\python-service-archetype\0.1.0\archetype.zip.sha256
```

Comparar el hash calculado con el del archivo `.sha256`. El resultado esperado es:

```text
dist/
├── cli/
│   ├── institutional_python_cli-0.1.1-py3-none-any.whl
│   └── institutional_python_cli-0.1.1.tar.gz
└── python-service-archetype/
    └── 0.1.1/
        ├── archetype.zip
        └── archetype.zip.sha256
```

Si `dist/cli` contiene builds anteriores, identificar los de esta versión;
no asumir que todo el directorio pertenece a la entrega actual.

## Entrega para publicación

Realizar estos pasos manualmente con una cuenta autorizada para publicar. Los
permisos de escritura son para el equipo publicador, no para los developers que
solo descargan. No sobrescribir una versión que ya haya sido distribuida.

### 1. Crear la ruta `cli` y cargar la herramienta

1. Abrir **Browse**, seleccionar el repositorio **Raw hosted** `python-archetypes`
   y pulsar **Upload component** (o entrar por **Upload** y seleccionar el repositorio).
2. En el campo de directorio de destino (**Directory**, según la versión de Nexus),
   indicar `cli/0.1.1` para el ejemplo de esta guía.
3. Agregar el wheel `.whl` y la distribución fuente `.tar.gz` de la misma versión.
   Conservar sus nombres reales, sin renombrarlos para simular otra versión.
4. Pulsar **Upload**. Si la interfaz admite un archivo por carga, repetir con el
   mismo directorio para el segundo archivo.
5. Volver a **Browse** y comprobar que ambos archivos aparecen bajo `cli/0.1.1/`.
   **NO CAMBIAR EL NOMBRE `cli` EN ESTE PROCEDIMIENTO.**

### 2. Crear la ruta de plantillas y cargar ZIP/SHA-256

1. Abrir nuevamente **Upload component** en el mismo repositorio.
2. Indicar `python-service-archetype/0.1.0` como directorio de destino, o la ruta acordada seguida
   de la versión, por ejemplo `arquetipos/python/0.1.0`.
3. Agregar `archetype.zip` y `archetype.zip.sha256`, verificados en el paso 5.
   Mantener ambos nombres y colocarlos juntos bajo la misma versión.
4. Pulsar **Upload** y comprobar en **Browse** que existen los dos archivos.
   No anunciar la versión mientras falte alguno: el descubrimiento de la CLI exige
   el par ZIP/SHA-256 completo.
5. Comunicar la URL base del repositorio y el directorio de plantillas al developer.
   Si se publicó en `arquetipos/python/0.1.0`, la configuración es:

   ```powershell
   $env:ARCHETYPE_NEXUS_TEMPLATE_PATH = "arquetipos/python"
   ```

La variable no incluye `python-archetypes`, la versión ni `archetype.zip`.
El directorio remoto no necesita coincidir con el directorio local de `dist/`.

### Correspondencia de archivos locales y rutas remotas

Este ejemplo usa `python-service-archetype` como directorio remoto; si se acordó otro, sustituir
solo ese prefijo en la columna **Ruta en Nexus**:

| Archivo local | Ruta en Nexus |
|---|---|
| `dist/cli/institutional_python_cli-0.1.1-py3-none-any.whl` | `cli/0.1.1/institutional_python_cli-0.1.1-py3-none-any.whl` |
| `dist/cli/institutional_python_cli-0.1.1.tar.gz` | `cli/0.1.1/institutional_python_cli-0.1.1.tar.gz` |
| `dist/python-service-archetype/0.1.0/archetype.zip` | `python-service-archetype/0.1.0/archetype.zip` |
| `dist/python-service-archetype/0.1.0/archetype.zip.sha256` | `python-service-archetype/0.1.0/archetype.zip.sha256` |

La base local de referencia es `http://localhost:8082/repository/python-archetypes/`;
confirmarla con el administrador u equipo a cargo.

Referencia: [carga de componentes en Nexus Repository](https://help.sonatype.com/en/uploading-components.html).
