# Migraciones preparadas — NO APLICADAS

Estos archivos están preparados y probados solo contra un PostgreSQL local de prueba. **No se han ejecutado contra Supabase.** Están fuera de `supabase/migrations/` a propósito para que ninguna herramienta los aplique sola.

| Orden | Archivo | Qué hace |
|---|---|---|
| 0 | `001_precheck_metadata_file_name.sql` | Solo SELECT. Ejecutar antes y revisar: NULL, vacíos, duplicados exactos y casi duplicados. |
| 1 | `001_metadata_file_name_unique.up.sql` | Añade `UNIQUE (file_name)`. Aborta sin cambios si hay NULL, vacíos o duplicados. |
| 1 | `001_metadata_file_name_unique.down.sql` | Rollback: quita la restricción. |
| 2 | `002_notification_reservations.up.sql` | Tabla de reservas atómicas de avisos de Slack. |
| 2 | `002_notification_reservations.down.sql` | Rollback: elimina la tabla (perdería el estado de reservas). |

## Por qué una restricción UNIQUE y no solo la prueba previa

Que hoy haya 0 duplicados en 19 filas no impide que aparezca uno entre la comprobación y la migración. La migración repite la comprobación dentro de la misma transacción y toma el bloqueo de la tabla antes de crear la restricción, de modo que no puede quedar una restricción a medias.

## Orden recomendado en Supabase (por Ana, con acceso)

1. Hacer copia de seguridad o punto de restauración.
2. Ejecutar `001_precheck…` y confirmar que todas las consultas de problema devuelven 0 filas.
3. Ejecutar `001…up.sql`. Comprobar `select conname from pg_constraint where conname='metadata_file_name_key'`.
4. Ejecutar `002…up.sql`.
5. Solo entonces importar/activar los workflows.

## Reservas de aviso (002): reconciliación manual

Estado `uncertain` o `inflight` abandonado = el mensaje pudo publicarse. Antes de reenviar, mirar el canal de Slack. Si se publicó:
`update public.notification_reservations set state='done', updated_at=now() where entry_id='<id>';`
Si no se publicó:
`delete from public.notification_reservations where entry_id='<id>';`
