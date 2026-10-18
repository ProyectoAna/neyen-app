-- ROLLBACK de 001. Quita la restricción; no toca datos.
-- Efecto: `on_conflict=file_name` volverá a fallar hasta reaplicar 001 o cambiar la insercion.
begin;
set local lock_timeout = '5s';
alter table public.metadata drop constraint if exists metadata_file_name_key;
commit;
