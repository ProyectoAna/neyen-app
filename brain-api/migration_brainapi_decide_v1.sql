-- brainapi_decide_v1: one atomic decision by Ana on one proposed item, at the version she saw.
-- Not a brain_* object (schema owned by Perplexity); does not alter any brain_* table.
-- Called only by brain-api with the service role. No grants to anon / authenticated / public.
create or replace function public.brainapi_decide(
  p_item uuid,
  p_version int,
  p_decision text,
  p_note text,
  p_actor uuid,          -- brain_participants.id of the approver (must be human + can_approve)
  p_auth_uid uuid,       -- Supabase Auth user id of the session (recorded in the audit row)
  p_api_version text
) returns table (id uuid, status text, version int)
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_item record;
  v_actor record;
  v_new_status text;
begin
  if p_decision is null or p_decision not in ('approve', 'reject') then
    raise exception 'invalid decision' using errcode = '22023';
  end if;
  if p_version is null or p_version < 1 then
    raise exception 'invalid version' using errcode = '22023';
  end if;
  if p_note is not null and length(p_note) > 2000 then
    raise exception 'note too long' using errcode = '22023';
  end if;

  select bp.id, bp.slug, bp.kind, bp.can_approve into v_actor
    from brain_participants bp where bp.id = p_actor;
  if not found or v_actor.kind <> 'human' or not v_actor.can_approve then
    raise exception 'actor cannot approve' using errcode = '42501';
  end if;

  -- Lock the row: concurrent decisions on the same item are serialised; the second one sees the new state.
  select bi.id, bi.status, bi.version, bi.archived_at into v_item
    from brain_items bi where bi.id = p_item for update;
  if not found then
    raise exception 'item not found' using errcode = 'P0002';
  end if;
  if v_item.archived_at is not null or v_item.status <> 'proposed' or v_item.version <> p_version then
    raise exception 'stale or already decided' using errcode = '40001';
  end if;

  v_new_status := case when p_decision = 'approve' then 'approved' else 'rejected' end;

  -- verification is deliberately not touched: approval is not verification.
  if v_new_status = 'approved' then
    update brain_items
       set status = 'approved', approved_by = p_actor, approved_at = now(), updated_by = p_actor
     where brain_items.id = p_item;
  else
    update brain_items
       set status = 'rejected', updated_by = p_actor
     where brain_items.id = p_item;
  end if;

  -- Same transaction: if this insert fails, the update above is rolled back too.
  insert into brain_audit_log (actor, action, target, detail)
  values (v_actor.slug,
          case when v_new_status = 'approved' then 'approve_item' else 'reject_item' end,
          p_item::text,
          jsonb_build_object('via', 'brain-api/approval-page', 'version', p_api_version,
                             'item_version_seen', p_version, 'auth_uid', p_auth_uid, 'note', p_note));

  return query select bi.id, bi.status, bi.version from brain_items bi where bi.id = p_item;
end;
$$;

revoke all on function public.brainapi_decide(uuid, int, text, text, uuid, uuid, text) from public, anon, authenticated;
grant execute on function public.brainapi_decide(uuid, int, text, text, uuid, uuid, text) to service_role;
