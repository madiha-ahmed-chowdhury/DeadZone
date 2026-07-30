-- DeadZone database schema (Postgres / Supabase)
--
-- Apply via the Supabase SQL editor, or:
--     supabase db reset       # local
--     supabase db push        # linked project

-- =========================================================
-- Extensions
-- =========================================================
create extension if not exists "pgcrypto";      -- gen_random_uuid()
create extension if not exists "uuid-ossp";

-- =========================================================
-- users — Telegram-identified civilians
-- =========================================================
create table if not exists public.users (
    id           uuid primary key default gen_random_uuid(),
    telegram_id  bigint unique,
    display_name text,
    created_at   timestamptz not null default now()
);

create index if not exists users_telegram_id_idx
    on public.users (telegram_id);

-- =========================================================
-- h3_hexes — per-cell rollups for the Dead Zone heatmap
-- =========================================================
create table if not exists public.h3_hexes (
    cell_id        text primary key,                -- h3 cell address at res 7
    centroid_lat   double precision not null,
    centroid_lng   double precision not null,
    last_pulse_at  timestamptz,
    pulse_count    integer     not null default 0,
    updated_at     timestamptz not null default now()
);

create index if not exists h3_hexes_last_pulse_idx
    on public.h3_hexes (last_pulse_at desc nulls last);

-- =========================================================
-- pulses — individual "I'm alive" signals
-- =========================================================
create table if not exists public.pulses (
    id           uuid primary key default gen_random_uuid(),
    user_id      uuid references public.users(id) on delete set null,
    raw_text     text        not null,
    place_text   text,
    lat          double precision,
    lng          double precision,
    h3_cell      text references public.h3_hexes(cell_id) on delete set null,
    confidence   text        not null default 'low',  -- high | medium | low
    matched_kind text        not null default 'unknown', -- gazetteer | centroid | unknown
    source       text        not null default 'bot',   -- bot | web | test
    created_at   timestamptz not null default now()
);

create index if not exists pulses_created_at_idx
    on public.pulses (created_at desc);

create index if not exists pulses_h3_cell_idx
    on public.pulses (h3_cell);

create index if not exists pulses_place_text_idx
    on public.pulses (place_text);

-- =========================================================
-- needs — categorized, priority-scored aid requests
-- (Need Broadcast Engine)
-- =========================================================
create table if not exists public.needs (
    id           uuid primary key default gen_random_uuid(),
    raw_text     text        not null,
    need_text    text        not null,
    category     text        not null default 'other', -- water | food | medical | shelter | other
    place_text   text,
    lat          double precision,
    lng          double precision,
    h3_cell      text references public.h3_hexes(cell_id) on delete set null,
    priority     integer     not null default 1,        -- 1 (low) .. 5 (high)
    urgent       boolean     not null default false,
    status       text        not null default 'open',   -- open | acknowledged | dispatched | fulfilled
    source       text        not null default 'bot',     -- bot | web | test
    created_at   timestamptz not null default now()
);

create index if not exists needs_created_at_idx
    on public.needs (created_at desc);

create index if not exists needs_category_idx
    on public.needs (category);

create index if not exists needs_priority_idx
    on public.needs (priority desc);

create index if not exists needs_status_idx
    on public.needs (status);

-- =========================================================
-- Realtime publication (Postgres Changes channel)
-- =========================================================
-- Drop & recreate to make the script idempotent.
do $$
begin
    if exists (
        select 1 from pg_publication where pubname = 'supabase_realtime'
    ) then
        execute 'alter publication supabase_realtime drop table if exists public.pulses';
        execute 'alter publication supabase_realtime drop table if exists public.h3_hexes';
        execute 'alter publication supabase_realtime drop table if exists public.needs';
    else
        create publication supabase_realtime;
    end if;
end
$$;

alter publication supabase_realtime add table public.pulses;
alter publication supabase_realtime add table public.h3_hexes;
alter publication supabase_realtime add table public.needs;

-- =========================================================
-- Row Level Security
-- =========================================================
-- The MVP is fully public on the read side — anyone with the URL can view
-- the live crisis map. Writes are restricted to the service role key,
-- which the FastAPI backend uses via SUPABASE_SERVICE_KEY.
alter table public.users     enable row level security;
alter table public.pulses    enable row level security;
alter table public.h3_hexes  enable row level security;
alter table public.needs     enable row level security;

drop policy if exists "read public pulses"  on public.pulses;
drop policy if exists "read public hexes"   on public.h3_hexes;
drop policy if exists "read public users"   on public.users;
drop policy if exists "read public needs"   on public.needs;

-- NOTE: users is intentionally NOT given a public read policy. It stores
-- telegram_id, which would let anyone holding the anon key deanonymize
-- who sent which pulse/need. The service-role key (used only by the
-- FastAPI backend) bypasses RLS and can still read it server-side.
create policy "read public pulses"
    on public.pulses for select
    using (true);

create policy "read public hexes"
    on public.h3_hexes for select
    using (true);

create policy "read public needs"
    on public.needs for select
    using (true);

-- =========================================================
-- Convenience view — most-recent pulse per hex
-- =========================================================
create or replace view public.v_recent_hexes as
    select
        h.cell_id::text         as h3_cell,
        h.centroid_lat,
        h.centroid_lng,
        h.last_pulse_at,
        h.pulse_count
    from public.h3_hexes h
    where h.last_pulse_at is not null;

grant select on public.v_recent_hexes to anon, authenticated;
grant select on public.pulses          to anon, authenticated;
grant select on public.h3_hexes        to anon, authenticated;
grant select on public.needs           to anon, authenticated;
-- public.users is NOT granted to anon/authenticated — see RLS note above.

-- =========================================================
-- Atomic hex-count increment (fixes a read-then-write race in the old
-- Python-side "select count, then upsert count+1" pattern, which could
-- lose increments under concurrent pulses).
-- =========================================================
create or replace function public.increment_hex(
    p_cell_id      text,
    p_centroid_lat double precision,
    p_centroid_lng double precision,
    p_when         timestamptz
) returns public.h3_hexes
language sql
as $$
    insert into public.h3_hexes (cell_id, centroid_lat, centroid_lng, last_pulse_at, pulse_count, updated_at)
    values (p_cell_id, p_centroid_lat, p_centroid_lng, p_when, 1, p_when)
    on conflict (cell_id) do update
        set pulse_count   = public.h3_hexes.pulse_count + 1,
            last_pulse_at = excluded.last_pulse_at,
            updated_at    = excluded.updated_at
    returning *;
$$;