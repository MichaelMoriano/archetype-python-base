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

El ZIP debe tener su archivo acompañante `archetype.zip.sha256`, tanto localmente
como en Nexus. No guardar credenciales en Git.

La CLI valida con uv y permite acceso a red para las dependencias. Después crea
el repositorio y el commit inicial en `main`, y opcionalmente una rama de trabajo.
No ejecuta SonarQube ni la auditoría online, no publica artefactos ni configura
remotos Git.
