-- SOLO LECTURA. Ejecutar antes de 001_metadata_file_name_unique.up.sql.
-- Todas las consultas de "problema" deben devolver 0 filas.

-- 1. NULL o vacíos (file_name es NOT NULL hoy, pero se comprueba el vacío)
select id, file_name from public.metadata
where file_name is null or btrim(file_name) = '';

-- 2. Duplicados exactos: bloquean la restricción
select file_name, count(*) as n, array_agg(id order by created_at) as ids
from public.metadata
group by file_name
having count(*) > 1;

-- 3. Casi duplicados (informativo: no bloquean UNIQUE, pero suelen ser el mismo registro)
select lower(btrim(file_name)) as normalizado, count(*) as n, array_agg(file_name) as variantes
from public.metadata
group by lower(btrim(file_name))
having count(*) > 1;

-- 4. Estado actual: no debe existir ya una restricción o índice único sobre file_name
select conname, pg_get_constraintdef(oid) from pg_constraint
where conrelid = 'public.metadata'::regclass and contype in ('u','p');
select indexname, indexdef from pg_indexes where schemaname = 'public' and tablename = 'metadata';

-- 5. Tamaño (para confirmar que el bloqueo será instantáneo)
select count(*) as filas from public.metadata;
