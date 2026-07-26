-- ============================================================
-- Agrega la tabla de tarifas para MitaToya
-- Corre esto en Supabase > SQL Editor > New query > Run
-- (además del supabase_schema.sql que ya corriste antes, no en vez de él)
-- ============================================================

create table if not exists precios (
  clave text primary key,
  valor numeric not null,
  actualizado_en timestamptz default now()
);

-- Precios iniciales (los mismos que ya tenías en el código).
-- Si una clave ya existe no la vuelve a insertar (no borra lo que ya editaste).
insert into precios (clave, valor) values
  ('traslado', 25),
  ('tour', 45),
  ('grupo', 80),
  ('renta', 35),
  ('hospedaje_triple', 0),
  ('hospedaje_doble', 0),
  ('deposito_porcentaje', 30),
  ('tipo_cambio', 36.6)
on conflict (clave) do nothing;

alter table precios enable row level security;

-- Cualquier visitante del sitio puede LEER las tarifas (para calcular el total)
create policy "leer_precios_publico"
  on precios for select
  to anon
  using (true);

-- Nota: nadie puede EDITAR precios con la clave pública (anon).
-- Solo el panel de Streamlit (que usa la clave privada service_role) puede cambiarlos.
