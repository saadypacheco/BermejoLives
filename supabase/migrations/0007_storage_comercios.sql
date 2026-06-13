-- ============================================================
-- Bermejo Live Market · 0007_storage_comercios
-- Bucket público para las fotos de local que carga el agente de campo.
-- Público = las imágenes se sirven por /storage/v1/object/public/... sin auth.
-- La subida la hace el backend con service_role (bypassa RLS).
-- ============================================================
insert into storage.buckets (id, name, public)
values ('comercios', 'comercios', true)
on conflict (id) do nothing;
