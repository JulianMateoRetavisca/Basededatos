# Flujo colaborativo para BD

## Objetivo

Permitir que varios usuarios trabajen en paralelo sobre cambios de esquema y datos controlados.

## Proceso por rama

1. Crear rama desde `main`.
2. Crear una migracion nueva en `migrations/`.
3. Ejecutarla en entorno de desarrollo.
4. Validar que sea segura y repetible.
5. Abrir Pull Request con descripcion tecnica.

## Checklist de PR

- El script tiene nombre versionado y descriptivo.
- El cambio incluye notas de impacto.
- El cambio incluye paso de rollback cuando aplique.
- La migracion fue probada en dev.
