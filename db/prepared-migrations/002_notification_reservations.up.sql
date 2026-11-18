-- NO APLICADA. Reserva atomica de avisos de Slack, compartida por todas las llamadas y replicas de n8n.
-- La atomicidad la da la clave primaria: dos INSERT simultaneos del mismo entry_id => uno gana, otro 409.
begin;
create table if not exists public.notification_reservations (
  entry_id   text primary key,
  state      text not null check (state in ('inflight', 'done', 'uncertain')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table public.notification_reservations enable row level security;
-- Sin politicas: solo el rol service_role (que ignora RLS) puede usarla. anon/authenticated, nada.
revoke all on public.notification_reservations from anon, authenticated;
commit;
