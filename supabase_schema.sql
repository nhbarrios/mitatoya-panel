-- ============================================================
-- Esquema de base de datos para MitaToya Tours & Taxi Ometepe
-- Cópialo y pégalo en: Supabase > tu proyecto > SQL Editor > New query > Run
-- ============================================================

-- Tabla de reservas: aquí caen las solicitudes que llegan desde el formulario del sitio
create table if not exists reservas (
  id bigint generated always as identity primary key,
  created_at timestamptz default now(),
  nombre text,
  documento text,
  telefono text,
  servicio text,          -- traslado / tour / grupo / renta / hospedaje
  habitacion text,        -- triple / doble / null
  fecha_inicio date,
  fecha_fin date,
  cantidad int,
  punto text,
  notas text,
  total numeric,
  deposito numeric,
  estado text default 'pendiente'   -- pendiente / confirmada / cancelada
);

-- Tabla de bloqueos: rangos de fechas NO disponibles por servicio/habitación
-- (esto es lo que tu index.html consulta para saber qué fechas mostrar como ocupadas)
create table if not exists bloqueos (
  id bigint generated always as identity primary key,
  servicio text,           -- renta / hospedaje
  habitacion text,         -- triple / doble / null (null = aplica a todo el servicio, ej. el único carro de renta)
  fecha_inicio date,
  fecha_fin date,
  motivo text
);

-- Seguridad a nivel de fila (obligatorio en Supabase)
alter table reservas enable row level security;
alter table bloqueos enable row level security;

-- Cualquier visitante del sitio puede CREAR una reserva (pero no leer las de otros)
create policy "insertar_reservas_publico"
  on reservas for insert
  to anon
  with check (true);

-- Cualquier visitante del sitio puede LEER los bloqueos (para pintar el calendario de disponibilidad)
create policy "leer_bloqueos_publico"
  on bloqueos for select
  to anon
  using (true);

-- Nota: nadie puede LEER reservas, ni EDITAR/BORRAR bloqueos, usando la clave pública (anon).
-- Esas operaciones solo las hace el panel de Streamlit, que usa la clave privada (service_role).
