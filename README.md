# Arquetipo Python Base para Servicios de IA

Base empresarial deliberadamente **sin RAG, LangGraph, Qdrant, LiteLLM ni memoria**.
Su responsabilidad es estandarizar lo que todos los microservicios Python de IA necesitan:

- Python 3.13 + `uv` + `uv.lock` versionado.
- FastAPI con API versionada `/api/v1`.
- `OriginId`, `SubOriginId`, `X-Request-Id`.
- validación JWT remota mediante GEN-SECURITY; el token no se interpreta localmente.
- errores controlados, configuración tipada, logging seguro y lifecycle de clientes HTTP.
- arquitectura hexagonal pragmática y composition root en `bootstrap/`.
- Ruff, mypy strict, Pytest y Docker non-root.

## Arranque local

Copia `.env.example` a `.env` y configura un GEN-SECURITY válido. Luego:

```powershell
uv sync
uv run uvicorn python_ai_service.bootstrap.main:create_app --factory --reload
```

Health público:

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

## Prueba de autenticación Basic

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

## Dónde agregar una capacidad

- reglas/modelos puros: `domain/`
- casos de uso y puertos: `application/`
- FastAPI: `api/v1/`
- SDKs, HTTP, DB, Qdrant, LiteLLM: `infrastructure/`
- selección de implementaciones: `bootstrap/composition.py`

No se crea una carpeta `v2` vacía. Se añade cuando realmente nace un contrato V2 incompatible; V1 puede convivir durante la migración.

## Análisis con SonarQube

`pysonar` es una dependencia de desarrollo; la imagen de producción utiliza
`uv sync --frozen --no-dev` y no la instala. El análisis utiliza el proyecto
`Archetype-Python-Base`, definido en `sonar-project.properties`.

Desde la raíz del repositorio, instala las dependencias y ejecuta las validaciones:

```powershell
uv sync --locked
.\scripts\validate.ps1
```

Continúa solo si las validaciones finalizaron correctamente. El script genera
`coverage.xml` con rutas relativas para que SonarQube importe la cobertura.
Ejecuta el script; solicita el token sin escribirlo en el historial:

```powershell
.\scripts\sonar.ps1
```

El token debe tener permiso de análisis para ese proyecto. No lo guardes en Git
ni en `sonar-project.properties`. La primera ejecución del scanner puede descargar
componentes adicionales y requiere conectividad. Un error del scanner, un timeout
o un Quality Gate fallido producen una ejecución fallida; revisa el mensaje y el
panel del proyecto para distinguir la causa.

Cuando el gate falla, el script consulta las condiciones del análisis recién
enviado y muestra el valor obtenido y el umbral, por ejemplo:
`Coverage: 89.25%; required >= 90%`. Distingue cobertura global y de código nuevo,
y muestra también otras condiciones fallidas sin atribuirlas a cobertura.
Las cifras proceden de SonarQube, no de una estimación del reporte local.
Si el token no permite consultar el resultado o el servidor no responde, informa
que el detalle no está disponible y conserva el fallo. No amplíes permisos sin
consultar la política del equipo. El diagnóstico no cambia el Quality Gate.

Para comprobar la configuración sin conectar al servidor ni enviar un análisis:

```powershell
$env:PYTHONUTF8 = "1"
uv run --locked pysonar --dry-run -Dsonar.host.url=http://localhost:9000
```

`PYTHONUTF8` evita errores de codificación en la salida del scanner en Windows.

El umbral local de cobertura es 90% (líneas y ramas combinadas por coverage.py);
la validación falla si no se alcanza. El Quality Gate corporativo se administra
en SonarQube y evalúa sus propias métricas globales y de código nuevo.
No se añaden exclusiones para forzar su aprobación.

## Flujo obligatorio de validación y seguridad

Desde la raíz del repositorio, el comando multiplataforma es:

```powershell
uv run --locked python scripts/check.py
```

Ejecuta **lockfile → Ruff → mypy → pruebas/cobertura → auditoría de dependencias
→ SonarQube** y se detiene ante el primer fallo. No construye, publica ni despliega
imágenes. `validate.ps1` conserva su propósito de validación local sin consultas
de vulnerabilidades; `sonar.ps1` permite ejecutar Sonar de forma independiente.
Ninguno de esos comandos aislados sustituye el flujo obligatorio.

Antes del paso Sonar deben existir `SONAR_HOST_URL` y `SONAR_TOKEN` en el entorno.
Para la ejecución local puedes usar un prompt seguro y limpiar el token al terminar:

```powershell
$env:SONAR_HOST_URL = "http://localhost:9000"
$token = Read-Host "SonarQube analysis token" -AsSecureString
try {
    $env:SONAR_TOKEN = [System.Net.NetworkCredential]::new("", $token).Password
    uv run --locked python scripts/check.py
    if ($LASTEXITCODE -ne 0) { throw "Required checks failed; do not publish or promote." }
} finally {
    Remove-Item Env:SONAR_TOKEN -ErrorAction SilentlyContinue
    $token.Dispose()
}
```

### Auditoría de dependencias Python

`pip-audit` y `packaging` son dependencias de desarrollo, no de producción.
Para ejecutar solo la auditoría:

```powershell
uv run --locked python scripts/audit_dependencies.py
```

El script exporta `uv.lock` con versiones exactas, dependencias transitivas y todos
los grupos (incluido desarrollo), sin incluir el propio proyecto. El exportado es
temporal: no se mantiene otro lockfile. Evalúa los marcadores de Python/plataforma
del entorno donde corre; para el despliegue Linux se debe ejecutar en ese entorno,
no tomar un resultado Windows como equivalente.

`pip-audit` consulta avisos de PyPI. Se desactiva su resolución/instalación mediante
`--no-deps --disable-pip`; los hashes se omiten únicamente en el inventario de
auditoría, que no instala paquetes. Se verifica que los nombres/versiones auditados
coincidan con el exportado y se rechazan dependencias omitidas, locales o sin pin.
La instalación del proyecto sigue usando `uv.lock` sin cambios.

La capa de política consulta NVD API 2.0 usando los alias CVE de cada aviso:

| Evidencia | Resultado |
|---|---|
| Mayor puntuación base CVSS v3.0/v3.1/v4.0 publicada por NVD >= 7.0 | Bloqueado (HIGH/CRITICAL), salida 1. |
| Todas las puntuaciones verificadas < 7.0, o sin avisos | Aprobado, salida 0. |
| Sin alias CVE, sin CVSS v3/v4, CVE rechazado, paquete omitido, fallo de consulta o reporte inconsistente | Verificación incompleta, salida 2; bloquea igualmente. |

Se toma el máximo entre fuentes/versiones/alias, no una media ni una estimación
de la severidad basada en la descripción. Un resultado incompleto no se clasifica
como HIGH: simplemente no autoriza continuar. Este criterio es explícito y no
promete cifras idénticas a otro scanner que seleccione fuentes distintas.
No hay excepciones ni correcciones automáticas implementadas. Los avisos incluyen
las versiones corregidas que publique PyPI; cualquier actualización requiere uv,
revisión y nuevas pruebas. Se conserva el reporte de avisos completos, no solo
los que bloquean.

Reportes generados (ignorados por Git bajo `build/`):

- `build/security/pip-audit.json`: inventario y avisos, o estado incompleto.
- `build/security/dependency-audit.json`: decisión, puntuaciones CVSS y hallazgos.

Puedes cambiar el directorio mediante `--report-dir <ruta>`. Cada ejecución
invalida el PASS anterior antes de consultar servicios. No se imprimen respuestas
HTTP de error, claves ni salidas de subprocesos potencialmente sensibles.

Si NVD falla, la consola identifica el CVE y la categoría: HTTP, timeout, red/TLS,
JSON inválido, esquema incompatible o puntuación ausente. El reporte agrega
`error_context` con esos datos, el estado HTTP cuando existe y una ruta de campos
saneada para errores de esquema. No se incluyen cuerpos HTTP ni valores recibidos.
Las métricas adicionales de NVD, como SSVC, no se interpretan como CVSS; las
puntuaciones CVSS soportadas siguen validándose estrictamente.

Configura `NVD_API_KEY` como secreto del entorno/CI si está disponible. No se lee
desde `.env` ni se acepta como argumento. Sin clave, el script espera 6 segundos
entre CVE nuevos; con clave, 0.6 segundos. Las consultas tienen timeout de 15 segundos
y no siguen redirects ni hacen reintentos automáticos. Los límites compartidos de
NVD pueden producir una ejecución incompleta: no se ignoran esos fallos.

La auditoría requiere acceso saliente a PyPI y NVD: se consultan identificadores
de paquetes/versiones y CVE, no se envía el código fuente de la aplicación.
No cubre vulnerabilidades del sistema operativo de la imagen ni acredita la
ausencia de paquetes maliciosos o vulnerabilidades todavía desconocidas.

### Integración con Tekton

El agente necesita Python 3.13, uv y `uv sync --locked`. Proporciona los secretos
por mecanismos del clúster y ejecuta el comando completo; cualquier salida no cero
debe fallar el paso. Conserva ambos reportes, incluso al fallar. No uses
`continueOnError`, `|| true` ni una actualización del manifiesto de Argo CD antes
de que aprueben todos los controles. El pipeline real de construcción/promoción
debe conectarse a este resultado; este repositorio no modifica el clúster.

Sonar no recibe automáticamente estos JSON. Su Quality Gate y la política CVSS
son controles independientes: ambos deben aprobar. Las pruebas locales de esta
integración simulan servicios y herramientas; no requieren tokens ni paquetes
vulnerables reales.

Referencias: [pip-audit](https://github.com/pypa/pip-audit),
[NVD API](https://nvd.nist.gov/developers/vulnerabilities).

En CI, genera el reporte antes del análisis y proporciona `SONAR_HOST_URL` y
`SONAR_TOKEN` mediante la configuración y los secretos del pipeline. `localhost`
solo sirve si el servidor está accesible en el mismo entorno del scanner. DevOps
puede ejecutar SonarScanner CLI en lugar de `pysonar`, reutilizando el mismo
archivo de propiedades y el reporte. No se configura aquí un pipeline específico.
