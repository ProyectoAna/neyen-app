-- NO APLICADA. Añade UNIQUE sobre metadata.file_name.
-- Necesaria para `POST /metadata?on_conflict=file_name` (nodo "Insertar sin duplicar").
begin;
set local lock_timeout = '5s';
lock table public.metadata in share row exclusive mode;

do $$
declare
  n_bad int;
  n_dup int;
begin
  select count(*) into n_bad from public.metadata where file_name is null or btrim(file_name) = '';
  select count(*) into n_dup from (
    select file_name from public.metadata group by file_name having count(*) > 1
  ) d;
  if n_bad > 0 or n_dup > 0 then
    raise exception 'ABORTADO: % filas con file_name nulo/vacio y % valores duplicados. No se cambia nada.', n_bad, n_dup;
  end if;
  if exists (select 1 from pg_constraint where conname = 'metadata_file_name_key' and conrelid = 'public.metadata'::regclass) then
    raise notice 'metadata_file_name_key ya existe; sin cambios.';
  else
    alter table public.metadata add constraint metadata_file_name_key unique (file_name);
  end if;
end $$;
commit;
