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

En CI, genera el reporte antes del análisis y proporciona `SONAR_HOST_URL` y
`SONAR_TOKEN` mediante la configuración y los secretos del pipeline. `localhost`
solo sirve si el servidor está accesible en el mismo entorno del scanner. DevOps
puede ejecutar SonarScanner CLI en lugar de `pysonar`, reutilizando el mismo
archivo de propiedades y el reporte. No se configura aquí un pipeline específico.
