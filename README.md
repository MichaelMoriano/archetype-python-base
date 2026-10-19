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

## Validación, vulnerabilidades y SonarQube

Ejecuta los comandos desde la raíz del repositorio, con Python 3.13 y uv.
Instala las dependencias de desarrollo:

```powershell
uv sync --locked
```

### Configuración

| Variable de entorno | Uso |
|---|---|
| `SONAR_HOST_URL` | URL accesible de SonarQube; localmente, `http://localhost:9000`. |
| `SONAR_TOKEN` | Token con permiso de análisis sobre `Archetype-Python-Base`. |
| `NVD_API_KEY` | Opcional y recomendable para consultar CVSS con menos restricciones de frecuencia. |

`check.py` lee el entorno: no solicita credenciales ni carga `.env` automáticamente.
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
| `uv run --locked python scripts/audit_dependencies.py` | Solo auditoría de dependencias y política CVSS. |
| `.\scripts\sonar.ps1` | Solo Sonar: solicita el token y muestra condiciones fallidas cuando puede consultarlas. Requiere generar primero `coverage.xml`. |

Estos comandos no sustituyen al flujo completo. El 90% local corresponde a la
métrica combinada de líneas y ramas de coverage.py; Sonar evalúa sus propias
métricas y condiciones. Su Quality Gate y la política CVSS son independientes:
los JSON de auditoría no se importan automáticamente en Sonar.

### Política de vulnerabilidades

Se exportan temporalmente las versiones exactas de `uv.lock`, con dependencias
transitivas y todos los grupos, incluido desarrollo. Se verifica que el inventario
auditado coincida; no se instala ni actualiza ningún paquete durante el análisis.
Los marcadores se evalúan para el Python y la plataforma actuales: un resultado
Windows no sustituye una auditoría Linux.

`pip-audit` obtiene avisos de PyPI y la capa adicional consulta NVD, tomando la
mayor puntuación base CVSS v3.0/v3.1/v4.0 entre fuentes y alias CVE:

| Salida del auditor | Resultado |
|---|---|
| `0` | Sin hallazgos o todos verificados por debajo de 7,0. |
| `1` | Bloqueado por HIGH/CRITICAL: CVSS >= 7,0. |
| `2` | Verificación incompleta: falta CVE/CVSS, hay dependencias omitidas o falla una consulta/validación. También detiene el flujo. |

No hay excepciones ni correcciones automáticas. Un hallazgo incluye paquete,
versión, CVE, CVSS y versiones corregidas disponibles. Un error NVD muestra CVE,
categoría y estado HTTP cuando existe, sin exponer claves ni cuerpos de respuesta.
No se audita el sistema operativo de la imagen ni se garantiza detectar paquetes
maliciosos o vulnerabilidades desconocidas.

### Reportes y revisión

| Archivo | Contenido |
|---|---|
| `coverage.xml` | Cobertura de las pruebas, importada por Sonar. |
| `build/security/pip-audit.json` | Inventario y avisos de dependencias. |
| `build/security/dependency-audit.json` | Estado `passed`, `blocked` o `incomplete`, puntuaciones y `error_context` si corresponde. |

Los reportes están ignorados por Git. Si falla la auditoría, revisa esos JSON,
corrige con uv y repite las pruebas y el análisis; no ignores el código de salida.
Puedes cambiar su directorio con `--report-dir <ruta>` en el auditor.
Sin `NVD_API_KEY`, las consultas de CVE nuevos se espacian 6 segundos; con clave,
0,6 segundos. Un fallo de acceso o límite de consultas no se considera aprobación.

Referencias: [pip-audit](https://github.com/pypa/pip-audit),
[NVD API](https://nvd.nist.gov/developers/vulnerabilities).
