# Basededatos

Este repositorio esta pensado para colaborar sobre cambios de base de datos en multiples ramas.

## Importante

- Git no permite cambios en tiempo real sobre una base SQL Server viva.
- Lo correcto es versionar migraciones SQL.
- Cada rama agrega sus scripts de migracion y luego se integran por Pull Request.

## Estructura

- `migrations/`: scripts SQL ordenados por version.
- `docs/`: guias de flujo para el equipo.

## Flujo de trabajo recomendado

1. Crear rama de trabajo: `feature/nombre-cambio-db`.
2. Agregar un archivo nuevo en `migrations/` con formato `YYYYMMDD_HHMM_descripcion.sql`.
3. Probar el script en una base de desarrollo compartida.
4. Abrir Pull Request.
5. Al hacer merge, ejecutar migraciones en QA y luego Produccion.

## Convenciones para migraciones

- Un script por cambio logico.
- Scripts idempotentes cuando sea posible.
- Evitar `DROP` sin respaldo o plan de rollback.
