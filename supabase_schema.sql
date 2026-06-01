create table if not exists public.output_files (
  id uuid primary key default gen_random_uuid(),
  source_path text not null unique,
  category text,
  filename text not null,
  file_ext text,
  content_json jsonb,
  content_text text,
  raw_content text not null,
  file_size integer,
  modified_at timestamptz,
  uploaded_at timestamptz not null default now()
);

create index if not exists output_files_category_idx
  on public.output_files (category);

create index if not exists output_files_filename_idx
  on public.output_files (filename);

alter table public.output_files enable row level security;

drop policy if exists "service_role can manage output files" on public.output_files;
create policy "service_role can manage output files"
  on public.output_files
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
