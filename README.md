# Arquetipo Python Base para Servicios de IA

-------
* Versión del arquetipo utilizado: `{{cookiecutter.archetype_version}}`.
* Versión inicial del servicio: `{{cookiecutter.project_version}}`.

La CLI completa la versión del arquetipo desde el manifiesto validado de la
plantilla seleccionada; no es un dato que deba ingresar el developer ni determina
la versión inicial de su servicio. Las variables se resuelven al generar el proyecto.

Base empresarial deliberadamente **sin RAG, LangGraph, Qdrant, LiteLLM ni memoria**.
Su responsabilidad es estandarizar lo que todos los microservicios Python de IA necesitan:

- Python 3.13 + `uv` + `uv.lock` versionado.
- FastAPI con API versionada `/api/v1`.
- `OriginId`, `SubOriginId`, `X-Request-Id`.
- validación JWT remota mediante GEN-SECURITY; el token no se interpreta localmente.
- errores controlados, configuración tipada, logging seguro y lifecycle de clientes HTTP.
- arquitectura hexagonal pragmática y composition root en `bootstrap/`.
- Ruff, mypy strict, Pytest y Docker non-root.

## 1. Requisitos del developer

- Windows con PowerShell; los ejemplos se ejecutan en esa terminal.
- Python **3.13**, [uv](https://docs.astral.sh/uv/getting-started/installation/) y
  Git disponibles en `PATH`.
- Identidad Git configurada: la CLI crea un commit inicial con la identidad existente.
- Acceso de lectura a Nexus y a las fuentes de dependencias; para el flujo completo,
  acceso a SonarQube, PyPI y NVD. Para probar autenticación, acceso a GEN-SECURITY.

```powershell
uv --version
uv python find 3.13
git --version
git var GIT_AUTHOR_IDENT
```

Si falta Python 3.13, instalarlo con `uv python install 3.13`.

## 2. Descargar e instalar la CLI

Solicitar al administrador de Nexus la URL del repositorio y la versión publicada.
Ingresar a Nexus con la cuenta de developer (rol dev con permisos de lectura):

1. En **Browse**, abrir el repositorio `{{cookiecutter.repository_nexus}}` y la carpeta **cli → versión publicada**.
2. Seleccionar el archivo de la CLI terminado en **`.whl`**.
3. En el panel derecho, sección **Summary**, hacer clic en el enlace **Path** para descargarlo.

No se necesita una cuenta administradora. Guardar el wheel e instalarlo con el
comando de abajo **antes** de ejecutar `create-python-project` desde la carpeta
donde se creará el servicio.

La base predeterminada de la CLI es:
`http://localhost:8082/repository/{{cookiecutter.repository_nexus}}/`.
`localhost` solo sirve cuando Nexus está en la misma máquina; en un entorno
compartido usar la URL HTTPS proporcionada por el administrador.

Si TI_EDO publicó la CLI **0.1.0** del ejemplo, descargar desde el navegador:

```text
http://localhost:8082/repository/{{cookiecutter.repository_nexus}}/cli/0.1.0/{{cookiecutter.cli_name}}
```

Guardar el archivo, por ejemplo, en `C:\ArchetypeTrial\downloads` e instalarlo:

```powershell
uv tool install --python 3.13 "C:\ArchetypeTrial\downloads\{{cookiecutter.cli_name}}"
create-python-project --help
```

El código actual construye la CLI **0.1.1**: si esa es la versión publicada por
TI_EDO, usar `cli/0.1.1/` y `{{cookiecutter.cli_name}}` en la descarga e instalación.
No confundir la versión de CLI con la de plantilla.
Si el comando no está en `PATH`, ejecutar `uv tool update-shell` y reabrir PowerShell.

## 3. Configurar Nexus y generar el proyecto

### Variables de entorno de la CLI

Estas son las variables propias del flujo de descarga y generación desde Nexus:

| Variable                        | Uso                                                                                                                    | Requisito y valor predeterminado                                                                                                                                                                      |
|---------------------------------|------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ARCHETYPE_NEXUS_URL`           | URL base del repositorio Raw, sin incluir `cli/`, `{{cookiecutter.archetype_directory}}/`, la versión ni el archivo.                            | Opcional; por defecto `http://localhost:8082/repository/{{cookiecutter.repository_nexus}}/`. En un entorno compartido, establecer la URL HTTPS proporcionada por el administrador. `--nexus-url` tiene prioridad. |
| `ARCHETYPE_NEXUS_TEMPLATE_PATH` | Directorio relativo de plantillas dentro del repositorio Raw, por ejemplo `{{cookiecutter.archetype_directory}}` o `arquetipos/python`.         | Obligatorio para Nexus, sin valor predeterminado. Ausente, vacío o inválido provoca un error local antes de consultar Nexus. No se exige con `--archive`.                                             |
| `NEXUS_USERNAME`                | Usuario con permiso de lectura; para descubrir versiones también necesita acceso al listado de assets del repositorio. | Obligatorio si se establece `NEXUS_TOKEN`. Sin ambas variables, la CLI intenta acceso anónimo.                                                                                                        |
| `NEXUS_TOKEN`                   | Token o password aceptado por Nexus mediante autenticación Basic.                                                      | Obligatorio si se establece `NEXUS_USERNAME`. No tiene un secreto predeterminado; no versionarlo ni escribirlo en ejemplos reales.                                                                    |

La CLI lee el entorno de la sesión; **no carga `.env`**. Las credenciales se usan
para consultar versiones y descargar la plantilla y su checksum. No configuran
automáticamente la descarga del wheel desde el navegador ni `uv tool install`.
Si se usa `--archive` con un ZIP local y su checksum, no se necesita acceso a Nexus.

La generación siempre valida con uv y crea el repositorio Git con su commit inicial
en `main`; una rama de trabajo opcional se crea después. Git y una identidad válida
son requisitos incluso al usar una plantilla local.

Para probar una plantilla local antes de publicarla:

```powershell
create-python-project --archive "C:\Plantillas\archetype.zip"
```

Debe existir `C:\Plantillas\archetype.zip.sha256` o la ruta del archivo. El archivo acompañante es
obligatorio tanto localmente como en Nexus; no se admite un hash manual como
alternativa. Un checksum ausente, inválido o que no coincide detiene la generación.

La ruta de plantilla debe usar segmentos separados por `/`, sin barras al inicio
o al final. Solo se admiten letras ASCII, números, `.`, `_` y `-` dentro de cada
segmento; no se permiten segmentos vacíos, `.` o `..`, espacios, URLs, escapes `%`
ni barras invertidas. La longitud máxima es de 512 caracteres.
Una ruta válida que no existe se detecta al consultar Nexus: no es el mismo error
que una variable ausente o inválida. La versión, el nombre, la rama y la descripción se seleccionan
con las preguntas/opciones de la CLI; `--output-dir` cambia el directorio de salida.
Las variables `cookiecutter.*` son datos de plantilla, no variables de entorno.

### Configurar la sesión

Para un Nexus autenticado, establecer estas cuatro variables en PowerShell antes
de ejecutar la CLI:

```powershell
$env:ARCHETYPE_NEXUS_URL = "http://localhost:8082/repository/{{cookiecutter.repository_nexus}}/"
$env:ARCHETYPE_NEXUS_TEMPLATE_PATH = "{{cookiecutter.archetype_directory}}"
$env:NEXUS_USERNAME = Read-Host "Usuario Nexus"
$nexusSecret = Read-Host "Token o password Nexus" -AsSecureString
$env:NEXUS_TOKEN = [System.Net.NetworkCredential]::new("", $nexusSecret).Password
```

La URL es la **base del repositorio Raw**, no la del wheel ni la del ZIP.
La CLI no carga `.env`; estas variables son exclusivas de la descarga, no de la
aplicación generada. _**OJITO: No guardar credenciales en comandos, Git ni documentación.**_

Crear una carpeta de trabajo fuera de cualquier repositorio Git o proyecto Python
y ejecutar allí la herramienta instalada; no se necesita clonar este arquetipo:

```powershell
New-Item -ItemType Directory -Force C:\ArchetypeTrial\services | Out-Null
Set-Location C:\ArchetypeTrial\services
create-python-project
```

Ejemplo interactivo, si `0.1.1` es la última plantilla publicada:

```text
Project name (e.g. gen_ai_demo): gen_ai_demo
Latest available archetype version: 0.1.1
Archetype version [0.1.1]: 0.1.1
Work branch [main]: feature/demo
Description [Generated institutional Python service]: Demo service
```

- Nombre: segmentos en minúsculas separados por `-` o `_`; al menos dos.
  `gen_ai_demo` genera la carpeta `gen-ai-demo` y el paquete `gen_ai_demo`.
- Versión: elegir una plantilla publicada; Enter acepta la más reciente mostrada.
  La consulta requiere permiso de listado de assets. Para fijarla sin listar:
  `create-python-project --template-version 0.1.1`.
- Rama: Enter conserva `main`; otra rama se crea después del commit inicial.
- Descripción: texto del servicio, sin secretos. La versión inicial del servicio
  es `0.1.0`, independiente de la CLI y de la plantilla.

La CLI descarga `<ARCHETYPE_NEXUS_TEMPLATE_PATH>/<versión>/archetype.zip` y su `.sha256`, comprueba
integridad, genera con Cookiecutter y ejecuta las validaciones locales antes del
commit inicial. No ejecuta Sonar ni la auditoría online, no configura remotos ni
publica. Si falla, detenerse y revisar el diagnóstico; no reutilizar una salida
incompleta. Solo consumir artefactos de un publicador confiable: el checksum
detecta corrupción, no acredita por sí solo la autenticidad del publicador.

Al finalizar, retirar las credenciales de la sesión:

```powershell
Remove-Item Env:NEXUS_USERNAME, Env:NEXUS_TOKEN, Env:ARCHETYPE_NEXUS_URL, Env:ARCHETYPE_NEXUS_TEMPLATE_PATH
$nexusSecret.Dispose()
```
---

## 4. Preparar el servicio y ejecutar el flujo completo

Ingresar al proyecto generado y crear su entorno en la ubicación final:

```powershell
Set-Location C:\ArchetypeTrial\services\gen-ai-demo
uv sync --locked
Copy-Item .env.example .env
```

Si `.env` ya existe, editarlo sin sobrescribirlo. Configurar las siguientes
variables con los valores del entorno; los secretos mostrados son marcadores:

```dotenv
APP_NAME=gen-ai-demo
APP_ENVIRONMENT=local
GEN_SECURITY_BASE_URL=http://localhost:8080
GEN_SECURITY_VALIDATE_TOKEN_PATH=/internal/validateToken
GEN_SECURITY_BASIC_AUTH_PATH=/internal/validateBasicAuth
GEN_SECURITY_USE_BASIC_AUTH=false
GEN_SECURITY_USERNAME=
GEN_SECURITY_PASSWORD=
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=REEMPLAZAR_CON_TOKEN_DE_ANALISIS
NVD_API_KEY=REEMPLAZAR_CON_CLAVE_NVD
```

Las URLs loopback son ejemplos locales. Confirmar las rutas de GEN-SECURITY con el
equipo del tercero. `GEN_SECURITY_USE_BASIC_AUTH` configura las credenciales de
servicio para la validación de JWT; **no habilita ni deshabilita** el endpoint de
prueba Basic. Si se establece en `true`, completar usuario y password del servicio.

**Antes de comenzar el desarrollo**, ejecutar desde la raíz del proyecto generado:

```powershell
uv run --locked --env-file .env python  scripts/check.py
```

Debe terminar con `All required checks passed. No image was published or deployed.`
Si falla, corregir la causa y repetir el flujo completo. La generación local no
garantiza que Sonar ni las dependencias actuales estén aprobados: comprobar ambos.
Las vulnerabilidades **altas y críticas deben resolverse** antes de continuar.
No versionar `.env`, tokens ni passwords.

## 5. Levantar y probar el servicio

Para el ejemplo generado `gen_ai_demo`:

```powershell
uv run --locked --env-file .env uvicorn gen_ai_demo.bootstrap.main:create_app --factory --reload
```

En otra terminal:

```powershell
curl.exe http://localhost:8000/api/v1/health/live
curl.exe http://localhost:8000/api/v1/health/ready
```

Son endpoints públicos; no sustituyen la prueba de conectividad con GEN-SECURITY.

### Prueba Basic contra GEN-SECURITY

`GET /api/v1/auth/basic/health` exige `OriginId`, `SubOriginId` y
`Authorization: Basic <base64(usuario:contraseña)>`. No requiere JWT ni devuelve
las credenciales. Reenvía el Basic completo al validador configurado mediante
`GEN_SECURITY_BASE_URL` y `GEN_SECURITY_BASIC_AUTH_PATH`; solo acepta
`returnCode == "000"` con una respuesta HTTP exitosa.

Con la aplicación ejecutándose, usa credenciales de prueba autorizadas:

```powershell
curl.exe --user "test-user" -H "OriginId: 26" -H "SubOriginId: 105" http://localhost:8000/api/v1/auth/basic/health
```

curl solicita la contraseña. Una validación correcta devuelve
un objeto con `status`, `origin`, `sub_origin` y `correlation_id`;
credenciales ausentes, malformadas o rechazadas producen 401 con el mensaje público
`Authentication failed.`, sin incluir detalles internos ni credenciales.
El endpoint realiza una llamada real al tercero; no hay bypass local.
Usa HTTPS fuera del entorno local: Base64 no cifra las credenciales.

## 6. Agregar una capacidad o flujo

- reglas/modelos puros: `domain/`
- casos de uso y puertos: `application/`
- FastAPI: `api/v1/`
- SDKs, HTTP, DB, Qdrant, LiteLLM: `infrastructure/`
- selección de implementaciones: `bootstrap/composition.py`

Definir primero el contrato HTTP y el caso de uso; declarar los puertos en
`application/`, implementar adaptadores en `infrastructure/` y conectarlos en
`bootstrap/`. Mantener middleware y dependencias compartidas en `api/common/`.
Agrupar esquemas Pydantic cohesivos en `*_schemas.py`; usar sufijos de rol cuando
faciliten la navegación (`*_router.py`, `*_port.py`, `*_adapter.py`, `*_use_case.py`).
`domain/` y `application/` no importan FastAPI, HTTPX, Pydantic settings ni SDKs.
No decodificar JWT localmente ni agregar bypass de seguridad. Incluir pruebas del
flujo y de sus fallos, actualizar el contrato/documentación y repetir `check.py`.

No se crea una carpeta `v2` vacía. Se añade cuando realmente nace un contrato V2 incompatible; V1 puede convivir durante la migración.

---

## 7. Validación, vulnerabilidades y SonarQube

Ejecuta los comandos desde la raíz del repositorio, con Python 3.13 y uv.
Instala las dependencias de desarrollo:

```powershell
uv sync --locked
```

### SonarQube local para desarrollo

Para las pruebas de desarrollo se recomienda ejecutar **SonarQube Community Build
v26.2.0.119303 en Docker**, separado de la aplicación Python. Esta es la versión
de referencia para este procedimiento; no es una recomendación de despliegue en
producción.

Usar una etiqueta de imagen correspondiente a esa versión, verificada en el
registro oficial, en lugar de `latest`. Publicar el puerto solo en loopback
(`127.0.0.1:9000:9000`) para las pruebas locales y conservar los datos mediante
volúmenes si se necesita mantener proyectos, tokens y configuración entre reinicios.
Con el scanner ejecutándose desde el host, configurar
`SONAR_HOST_URL=http://localhost:9000`.

Consultar la [instalación oficial con Docker](https://docs.sonarsource.com/sonarqube-community-build/server-installation/from-docker-image/set-up-and-start-container).

### Quality Gate de referencia

Las siguientes condiciones corresponden a la captura de referencia del equipo;
no se configuran automáticamente desde este repositorio. Crear o seleccionar el
Quality Gate en SonarQube y asociarlo al proyecto. Las tablas indican cuándo
**falla** cada condición.

| Scope | Metric | Failure condition |
|---|---|---|
| New Code | Issues | Greater than 0. |
| New Code | Security Hotspots Reviewed | Less than 100%. |
| New Code | Coverage | Less than 90%. |
| New Code | Duplicated Lines (%) | Greater than 40%. |
| New Code | Maintainability Rating | Worse than A. |
| New Code | Reliability Rating | Worse than A. |
| New Code | Security Rating | Worse than A. |
| Overall Code | Coverage | Less than 90%. |
| Overall Code | Duplicated Blocks | Greater than 40 blocks. |
| Overall Code | Maintainability Issues | Greater than 80. |

La cobertura local y el Quality Gate son controles distintos: alcanzar el 90 %
en las pruebas no garantiza aprobar las demás condiciones de SonarQube.

### Configuración

| Variable de entorno | Uso |
|---|---|
| `SONAR_HOST_URL` | URL accesible de SonarQube; localmente, `http://localhost:9000`. |
| `SONAR_TOKEN` | Obligatorio. Token con permiso de análisis sobre `sonar.projectKey` en `sonar-project.properties`, cuyo valor en el proyecto generado es `{{cookiecutter.project_name}}`: el nombre indicado por el developer, normalizado por la CLI. |
| `NVD_API_KEY` | Obligatoria para este procedimiento del developer. Clave de la API NVD para consultar CVSS con menor restricción de frecuencia. |

Guardar estas variables en `.env`, como en el paso 4. Obtener el token de análisis
en SonarQube y solicitar la clave en [NVD](https://nvd.nist.gov/developers/request-an-api-key).
El scanner se instala con las dependencias de desarrollo mediante uv; puede requerir
acceso adicional para aprovisionar sus componentes/runtime en la primera ejecución.
`NVD_API_KEY` sigue siendo opcional en la implementación: el requisito aquí es
operativo, no una validación automática de presencia en el script.

`check.py` lee el entorno: no solicita credenciales ni carga `.env` automáticamente;
`uv run --env-file .env` carga el archivo para este comando y sus procesos hijos.
No guardes claves en Git ni en `sonar-project.properties`, que define el proyecto,
las fuentes, las pruebas y la ubicación de `coverage.xml`.
Se requiere conectividad a SonarQube, PyPI y NVD; el scanner puede descargar
componentes adicionales en su primera ejecución.

### Flujo completo

Con las variables configuradas, ejecuta:

```powershell
uv run --locked --env-file .env python  scripts/check.py
```

El orden es **lockfile → Ruff lint/formato → mypy → pruebas y cobertura mínima
del 90% → auditoría de dependencias → Sonar y su Quality Gate**.
Cualquier fallo detiene los pasos posteriores. El comando no construye, publica
ni despliega imágenes.

### Ejecuciones individuales

| Comando | Alcance |
|---|---|
| `.\scripts\validate.ps1` | Lockfile, Ruff, mypy, pruebas y generación de `coverage.xml`; no audita dependencias ni ejecuta Sonar. |
| `uv run --locked --env-file .env python scripts/audit_dependencies.py` | Solo auditoría de dependencias y política CVSS. |
| `uv run --locked --env-file .env pysonar --sonar-qualitygate-wait` | Solo Sonar usando `.env`. Requiere generar primero `coverage.xml`. |

Estos comandos no sustituyen al flujo completo. El 90% local corresponde a la
métrica combinada de líneas y ramas de coverage.py; Sonar evalúa sus propias
métricas y condiciones. Su Quality Gate y la política CVSS son independientes:
los JSON de auditoría no se importan automáticamente en Sonar.

Si Sonar falla dentro de `check.py`, el flujo intenta consultar las condiciones
fallidas del análisis actual y muestra la métrica, el valor obtenido y el umbral
requerido. Usa `SONAR_HOST_URL` y `SONAR_TOKEN`, sin solicitar ni imprimir el token;
los metadatos temporales se crean fuera del proyecto y se eliminan al terminar.
Las consultas de diagnóstico usan HTTPS, excepto en loopback para pruebas locales,
sin seguir redirecciones. Si el servidor o los permisos no permiten recuperar los
detalles, muestra una advertencia y conserva el fallo bloqueante. El comando
individual `pysonar` sigue disponible, pero no incorpora este diagnóstico adicional.

### Política de vulnerabilidades

Se auditan las versiones exactas de `uv.lock`, incluyendo dependencias transitivas y de desarrollo, sin instalar ni actualizar paquetes. Los resultados corresponden al sistema operativo y versión de Python donde se ejecuta el análisis.

**Proceso de auditoría:**

1. **pip-audit:** identifica vulnerabilidades en las dependencias mediante avisos de PyPI.
2. **NVD:** consulta las puntuaciones CVSS asociadas a los identificadores CVE.
3. **OSV:** se utiliza como alternativa cuando no existe un CVE o NVD no proporciona una puntuación verificable.
4. **Evaluación:** se aplica la mayor puntuación base CVSS v3.0, v3.1 o v4.0 validada mediante la biblioteca `cvss`.

**Seguridad de consultas OSV:**

- **Endpoint:** `https://api.osv.dev/v1/vulns/<identificador>`.
- Solo se transmite el identificador público de la vulnerabilidad.
- No se envían código fuente, dependencias ni credenciales.
- Se utilizan conexiones sin redirecciones ni proxies del entorno, con timeout de 15 segundos y límite de respuesta de 1 MiB.
- Solo se aceptan vulnerabilidades vigentes cuyo identificador, paquete PyPI y versión afectada coincidan con los datos auditados.

**Requisito de red:** acceso HTTPS a `api.osv.dev`.

**Importante:** las puntuaciones temporales o ambientales no reducen el CVSS base utilizado para determinar el umbral de severidad.

| Salida del auditor | Resultado |
|---|---|
| `0` | Sin hallazgos o todos verificados por debajo de 7,0. |
| `1` | Evaluación completa y bloqueada por HIGH/CRITICAL: CVSS >= 7,0. |
| `2` | Verificación incompleta: NVD y el respaldo OSV no permiten completar la evaluación, hay dependencias omitidas o falla una validación global. Tiene prioridad aunque también existan hallazgos HIGH/CRITICAL; detiene el flujo. |

La auditoría bloquea la aprobación ante vulnerabilidades **HIGH (7.0–8.9)** y **CRITICAL (9.0–10.0)**. No se permite reducir el umbral, omitir la auditoría ni aplicar excepciones. Las correcciones deben realizarse manualmente.

Los hallazgos de menor severidad no bloquean esta política CVSS, pero **SonarQube mantiene sus propios criterios de aprobación**.

**Reporte de vulnerabilidades:**

- Se registran todos los hallazgos: paquete, versión, identificadores, alias, versiones corregidas y severidad/CVSS verificable.
- `sources`: identifica las fuentes consultadas (NVD/OSV).
- `score_evidence`: conserva identificadores, puntuaciones y vectores utilizados.
- `cvss_by_cve`: contiene exclusivamente puntuaciones obtenidas de NVD.
- `warnings`: registra errores de la fuente primaria cuando la fuente alternativa completa la evaluación.
- `assessment_status: incomplete`: identifica evaluaciones sin evidencia suficiente, con `severity: UNVERIFIED` y `cvss: null`.

**Criterios de ejecución:**

- El auditor continúa evaluando todos los hallazgos, aunque alguno presente errores.
- El resumen incluye vulnerabilidades detectadas, hallazgos HIGH/CRITICAL verificados y evaluaciones incompletas.
- Las evaluaciones incompletas mantienen el bloqueo con **código de salida `2`**.
- Los errores de NVD muestran el CVE, la categoría y el estado HTTP disponible, sin exponer credenciales ni respuestas completas.

**Limitaciones:** la auditoría no evalúa vulnerabilidades del sistema operativo de la imagen ni garantiza identificar paquetes maliciosos o vulnerabilidades desconocidas.

---
### Reportes y revisión

| Archivo | Contenido |
|---|---|
| `coverage.xml` | Cobertura de las pruebas, importada por Sonar. |
| `build/security/pip-audit.json` | Inventario y avisos de dependencias. |
| `build/security/dependency-audit.json` | Estado `passed`, `blocked` o `incomplete`, todos los hallazgos evaluados/pendientes, errores por hallazgo y resumen de conteos. Los fallos globales pueden incluir `error_context`. |

Los reportes están ignorados por Git. Si falla la auditoría, revisa esos JSON,
corrige con uv y repite las pruebas y el análisis; no ignores el código de salida.
Puedes cambiar su directorio con `--report-dir <ruta>` en el auditor.
Sin `NVD_API_KEY`, las consultas de CVE nuevos se espacian 6 segundos; con clave,
0,6 segundos. Un fallo de acceso o límite de consultas no se considera aprobación.

Arquitectura y flujo de extensión: [guía de arquitectura](docs/ARCHITECTURE.md).

Referencias: [pip-audit](https://github.com/pypa/pip-audit),
[NVD API](https://nvd.nist.gov/developers/vulnerabilities).

### Autor

- **Área:** Ecosistemas Digitales y Open Finance
- **Correo:** [TI_EDO@cajaica.pe](mailto:TI_EDO@cajaica.pe)
