-- El veredicto de la IA se guarda en la publicación, no en la pantalla.
--
-- POR QUÉ
-- =======
-- Hasta ahora la IA opinaba cuando el moderador apretaba un botón, y la
-- opinión vivía en el estado del navegador: se iba al recargar. O sea que
-- primero miraba una persona y después opinaba la máquina — al revés.
--
-- Con el veredicto en la fila, un proceso lo pide apenas entra la publicación
-- y la cola llega ORDENADA al moderador: lo dudoso y lo rechazable arriba, lo
-- limpio abajo. Con tres ofertas por día da igual; con cincuenta es la
-- diferencia entre revisar y no revisar.

alter table publicaciones add column if not exists ia_veredicto  text
  check (ia_veredicto in ('aprobar', 'rechazar', 'dudoso'));
alter table publicaciones add column if not exists ia_motivo     text;
alter table publicaciones add column if not exists ia_confianza  numeric(3,2)
  check (ia_confianza between 0 and 1);
alter table publicaciones add column if not exists ia_revisado_at timestamptz;

-- Lo que el worker busca: pendientes sin veredicto. Parcial a propósito — es
-- el único filtro que corre seguido, y la tabla va a crecer.
create index if not exists idx_publicaciones_sin_ia
  on publicaciones (created_at)
  where estado = 'pendiente' and ia_veredicto is null;
