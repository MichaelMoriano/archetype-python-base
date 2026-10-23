# CLI institucional para proyectos Python

Herramienta para generar servicios Python desde una plantilla versionada de
Nexus o un ZIP local, mediante Cookiecutter. Requiere Python 3.13, uv y Git con
identidad configurada.

## Uso

Después de instalar el wheel publicado por el equipo responsable, ejecutar desde
una carpeta de trabajo fuera de cualquier repositorio Git o proyecto Python:

```powershell
create-python-project --help
create-python-project
```

## Configuración de Nexus

Establecer las variables en la sesión de PowerShell; la CLI no carga `.env`:

| Variable | Uso |
|---|---|
| `ARCHETYPE_NEXUS_URL` | URL base del repositorio Raw. Si se omite, usa `http://localhost:8082/repository/python-archetypes/`. Usar HTTPS fuera de loopback. |
| `ARCHETYPE_NEXUS_TEMPLATE_PATH` | Directorio relativo de plantillas en Nexus. Obligatorio, sin valor predeterminado. |
| `NEXUS_USERNAME` | Usuario de lectura y listado de assets, si Nexus exige autenticación. |
| `NEXUS_TOKEN` | Token o contraseña para Basic; debe configurarse junto con `NEXUS_USERNAME`. |

Para usar una plantilla local sin Nexus:

```powershell
create-python-project --archive "C:\Plantillas\archetype.zip"
```

El nombre remoto está definido por el mantenedor en `ARCHETYPE_ARCHIVE_NAME`
(predeterminado: `archetype.zip`). La CLI busca ese ZIP y su `<nombre>.sha256`.
Cambiar el nombre remoto requiere una CLI actualizada, no una variable de entorno.
Con `--archive` se admite otro nombre local, como `archetype_python.zip`, y su
`archetype_python.zip.sha256`. Hasta 128 caracteres, inicio con letra o número
ASCII, solo letras, números, guiones y guiones bajos antes de la extensión exacta
`.zip`; sin nombres reservados de Windows. No guardar credenciales en Git.

La CLI valida con uv y permite acceso a red para las dependencias. Después crea
el repositorio y el commit inicial en `main`, y opcionalmente una rama de trabajo.
No ejecuta SonarQube ni la auditoría online, no publica artefactos ni configura
remotos Git.

## Personalizar los mensajes

Las preguntas, ayudas y mensajes principales están centralizados en
`src/institutional_archetype_cli/messages.py`. Conservar los campos de formato
`{version}`, `{description}`, `{path}`, `{name}` y `{message}` al editar sus textos.
Cambiar el texto de una pregunta no modifica las validaciones ni los valores
predeterminados de rama y versión: estos siguen definidos en `cli.py`.
`DEFAULT_DESCRIPTION` sí establece la descripción usada al presionar Enter.
Los errores técnicos de las
funciones de validación permanecen en `cli.py` y `support.py`.

El módulo se distribuye dentro del wheel de la CLI, no en el ZIP del servicio.
Para que los developers reciban los cambios, publicar e instalar una CLI actualizada.
