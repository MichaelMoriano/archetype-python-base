# Arquitectura del arquetipo base

## Regla principal

El arquetipo base estandariza plataforma, no capacidades IA. Un servicio clonado incorpora únicamente los puertos, casos de uso y adaptadores que su responsabilidad requiere.

```text
HTTP -> API v1 -> application -> ports -> infrastructure
                         ^          |
                         |          v
                       domain   GEN-SECURITY / APIs / DB / IA
```

`domain` y `application` no importan frameworks ni SDKs externos.

## Versionamiento

`api/common` contiene elementos transversales que no pertenecen a una versión del contrato. `api/v1` contiene routers y schemas del contrato V1. No se crea `v2` hasta que exista un cambio incompatible real.

## Bootstrap

`bootstrap/main.py` crea FastAPI. `bootstrap/lifespan.py` administra recursos. `bootstrap/composition.py` selecciona adaptadores. Esta separación aproxima el concepto de módulo bootstrap utilizado por los arquetipos Java sin convertir Python en Java.
