-- DeadZone database schema (Postgres / Supabase)

-- =========================================================
-- Extensions
-- =========================================================
create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";

-- =========================================================
-- users
-- =========================================================
create table if not exists public.users (
    id uuid primary key default gen_random_uuid(),
    telegram_id bigint unique,
    display_name text,
    created_at timestamptz not null default now()
);

create index if not exists users_telegram_id_idx
on public.users (telegram_id);

-- =========================================================
-- h3_hexes
-- =========================================================
create table if not exists public.h3_hexes (
    cell_id text primary key,
    centroid_lat double precision not null,
    centroid_lng double precision not null,
    last_pulse_at timestamptz,
    pulse_count integer not null default 0,
    updated_at timestamptz not null default now()
);

create index if not exists h3_hexes_last_pulse_idx
on public.h3_hexes (last_pulse_at desc nulls last);

-- =========================================================
-- pulses
-- =========================================================
create table if not exists public.pulses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references public.users(id) on delete set null,
    raw_text text not null,
    place_text text,
    lat double precision,
    lng double precision,
    h3_cell text references public.h3_hexes(cell_id) on delete set null,
    confidence text not null default 'low',
    matched_kind text not null default 'unknown',
    source text not null default 'bot',
    created_at timestamptz not null default now()
);

create index if not exists pulses_created_at_idx
on public.pulses (created_at desc);

create index if not exists pulses_h3_cell_idx
on public.pulses (h3_cell);

create index if not exists pulses_place_text_idx
on public.pulses (place_text);

-- =========================================================
-- needs
-- =========================================================
create table if not exists public.needs (
    id uuid primary key default gen_random_uuid(),
    raw_text text not null,
    need_text text not null,
    category text not null default 'other',
    place_text text,
    lat double precision,
    lng double precision,
    h3_cell text references public.h3_hexes(cell_id) on delete set null,
    priority integer not null default 1,
    urgent boolean not null default false,
    status text not null default 'open',
    source text not null default 'bot',
    created_at timestamptz not null default now()
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
-- Row Level Security
-- =========================================================
alter table public.users enable row level security;
alter table public.pulses enable row level security;
alter table public.h3_hexes enable row level security;
alter table public.needs enable row level security;

drop policy if exists "read public pulses" on public.pulses;
drop policy if exists "read public hexes" on public.h3_hexes;
drop policy if exists "read public users" on public.users;
drop policy if exists "read public needs" on public.needs;

create policy "read public pulses"
on public.pulses
for select
using (true);

create policy "read public hexes"
on public.h3_hexes
for select
using (true);

create policy "read public needs"
on public.needs
for select
using (true);

grant select on public.pulses to anon, authenticated;
grant select on public.h3_hexes to anon, authenticated;
grant select on public.needs to anon, authenticated;

-- =========================================================
-- View
-- =========================================================
create or replace view public.v_recent_hexes as
select
    h.cell_id as h3_cell,
    h.centroid_lat,
    h.centroid_lng,
    h.last_pulse_at,
    h.pulse_count
from public.h3_hexes h
where h.last_pulse_at is not null;

grant select on public.v_recent_hexes to anon, authenticated;

-- =========================================================
-- Atomic increment function
-- =========================================================
create or replace function public.increment_hex(
    p_cell_id text,
    p_centroid_lat double precision,
    p_centroid_lng double precision,
    p_when timestamptz
)
returns public.h3_hexes
language sql
as $$
    insert into public.h3_hexes (
        cell_id,
        centroid_lat,
        centroid_lng,
        last_pulse_at,
        pulse_count,
        updated_at
    )
    values (
        p_cell_id,
        p_centroid_lat,
        p_centroid_lng,
        p_when,
        1,
        p_when
    )
    on conflict (cell_id)
    do update
    set
        pulse_count = public.h3_hexes.pulse_count + 1,
        last_pulse_at = excluded.last_pulse_at,
        updated_at = excluded.updated_at
    returning *;
$$;