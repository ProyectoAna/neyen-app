-- ROLLBACK de 002. Borra la tabla y TODO el estado de reservas (se perderia la proteccion contra duplicados).
begin;
drop table if exists public.notification_reservations;
commit;
