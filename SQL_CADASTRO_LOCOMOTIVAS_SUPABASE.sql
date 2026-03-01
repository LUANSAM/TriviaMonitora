-- SQL para habilitar o cadastro de locomotivas no Supabase
-- Versão com tabela específica: public.locomotivas

begin;

create extension if not exists pgcrypto;

create table if not exists public.locomotivas (
  id uuid primary key default gen_random_uuid(),
  tag text not null,
  modelo text not null,
  base text not null,
  combustivel text not null,
  volume_tanque numeric(12,2) not null,
  nivel_atual numeric(5,2) not null default 0,
  exibe_nivel boolean not null default true,
  foto_path text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

alter table public.locomotivas add column if not exists tag text;
alter table public.locomotivas add column if not exists modelo text;
alter table public.locomotivas add column if not exists base text;
alter table public.locomotivas add column if not exists combustivel text;
alter table public.locomotivas add column if not exists volume_tanque numeric(12,2);
alter table public.locomotivas add column if not exists nivel_atual numeric(5,2) default 0;
alter table public.locomotivas add column if not exists exibe_nivel boolean default true;
alter table public.locomotivas add column if not exists foto_path text;
alter table public.locomotivas add column if not exists created_at timestamptz default timezone('utc', now());
alter table public.locomotivas add column if not exists updated_at timestamptz default timezone('utc', now());

update public.locomotivas set nivel_atual = 0 where nivel_atual is null;
update public.locomotivas set exibe_nivel = true where exibe_nivel is null;
update public.locomotivas set base = 'Não informada' where base is null or trim(base) = '';

alter table public.locomotivas
  alter column tag set not null,
  alter column modelo set not null,
  alter column base set not null,
  alter column combustivel set not null,
  alter column volume_tanque set not null,
  alter column nivel_atual set not null,
  alter column exibe_nivel set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'ck_locomotivas_combustivel'
      and conrelid = 'public.locomotivas'::regclass
  ) then
    alter table public.locomotivas
      add constraint ck_locomotivas_combustivel
      check (combustivel in ('Diesel S10', 'Diesel S500'));
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'ck_locomotivas_volume_tanque'
      and conrelid = 'public.locomotivas'::regclass
  ) then
    alter table public.locomotivas
      add constraint ck_locomotivas_volume_tanque
      check (volume_tanque > 0);
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'ck_locomotivas_nivel_atual'
      and conrelid = 'public.locomotivas'::regclass
  ) then
    alter table public.locomotivas
      add constraint ck_locomotivas_nivel_atual
      check (nivel_atual between 0 and 100);
  end if;
end $$;

create or replace function public.set_updated_at_locomotivas()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists trg_set_updated_at_locomotivas on public.locomotivas;
create trigger trg_set_updated_at_locomotivas
before update on public.locomotivas
for each row
execute function public.set_updated_at_locomotivas();

create unique index if not exists uq_locomotivas_tag_lower
  on public.locomotivas ((lower(trim(tag))));
create index if not exists idx_locomotivas_modelo
  on public.locomotivas ((lower(trim(modelo))));
create index if not exists idx_locomotivas_base
  on public.locomotivas ((lower(trim(base))));
create index if not exists idx_locomotivas_combustivel
  on public.locomotivas (combustivel);
create index if not exists idx_locomotivas_created_at
  on public.locomotivas (created_at desc);

-- Bucket para fotos das locomotivas
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'veiculos',
  'veiculos',
  true,
  5242880,
  array['image/jpeg', 'image/png', 'image/webp']::text[]
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

-- Políticas para permitir upload/listagem de fotos pelo backend atual (usa anon key no storage)
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'veiculos_public_read'
  ) then
    create policy veiculos_public_read
      on storage.objects
      for select
      to public
      using (bucket_id = 'veiculos');
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'veiculos_anon_insert'
  ) then
    create policy veiculos_anon_insert
      on storage.objects
      for insert
      to anon
      with check (bucket_id = 'veiculos');
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'veiculos_anon_update'
  ) then
    create policy veiculos_anon_update
      on storage.objects
      for update
      to anon
      using (bucket_id = 'veiculos')
      with check (bucket_id = 'veiculos');
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'storage' and tablename = 'objects' and policyname = 'veiculos_anon_delete'
  ) then
    create policy veiculos_anon_delete
      on storage.objects
      for delete
      to anon
      using (bucket_id = 'veiculos');
  end if;
end $$;

commit;

-- Exemplo de insert manual (opcional)
-- insert into public.locomotivas (tag, modelo, base, combustivel, volume_tanque, nivel_atual)
-- values (
--   'LMT-001',
--   'EMD GT42',
--   'Pátio Campinas',
--   'Diesel S10',
--   5000,
--   40
-- );
