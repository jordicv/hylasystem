# HYLA CRM (MVP)

MVP en Flask + Supabase (Auth, Postgres, Storage) para gestión de posibles clientes.

## Requisitos
- Python 3.11+
- Proyecto Supabase activo

## Configuración en Supabase
1) Crea un proyecto en Supabase.
2) En **Authentication**, habilita Email/Password.
3) En **Storage**, crea un bucket llamado `lead-images` (o el nombre que definas en `SUPABASE_STORAGE_BUCKET`).
4) En **Settings > API**, copia las claves **Legacy anon** y **Legacy service_role** (las nuevas `sb_publishable_`/`sb_secret_` no funcionan con supabase-py):
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY` (legacy anon)
   - `SUPABASE_SERVICE_ROLE_KEY` (legacy service_role, necesaria para crear usuarios desde el backend)

## Esquema SQL (Tablas)
Ejecuta en el SQL editor de Supabase:

```sql
create table if not exists users (
  id uuid primary key,
  name text not null,
  email text not null unique,
  role text not null,
  status text not null,
  city text not null,
  team_id text not null,
  manager_user_id uuid null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists leads (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references users(id),
  demo_user_id uuid null references users(id),
  team_id text not null,
  first_name text not null,
  last_name text not null,
  occupation text,
  whatsapp_number text not null,
  address_line text,
  city text,
  region text,
  country text default 'Chile',
  status text not null,
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists lead_images (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references leads(id),
  storage_path text not null,
  url text,
  uploaded_by uuid not null references users(id),
  uploaded_at timestamptz default now()
);

create table if not exists audit_logs (
  id uuid primary key default gen_random_uuid(),
  timestamp timestamptz default now(),
  actor_user_id uuid,
  actor_name text,
  action text not null,
  entity_type text not null,
  entity_id text not null,
  team_id text,
  before jsonb,
  after jsonb
);

-- Si ya tenias la tabla leads creada:
alter table leads add column if not exists demo_user_id uuid null references users(id);
```

## Variables de entorno
Crea un archivo `.env` (puedes copiar `.env.example`) con:
- `FLASK_SECRET_KEY`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_NAME`
- `BOOTSTRAP_ADMIN_CITY`

## Ejecución
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

## Notas
- El primer arranque crea un **ADMIN** usando las variables `BOOTSTRAP_*` (requiere `SUPABASE_SERVICE_ROLE_KEY`).
- El login usa Supabase Auth (email/contraseña).
- Los leads admiten imágenes (jpg/jpeg/png/webp) hasta 5MB en Supabase Storage.
