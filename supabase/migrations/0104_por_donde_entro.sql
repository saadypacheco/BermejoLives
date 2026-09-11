-- Por dónde entró cada mensaje: WAHA o la API oficial de Meta.
--
-- El Plan B —la API oficial— ya está construido y el webhook acepta las dos
-- fuentes. Lo que faltaba es poder DEMOSTRAR que funciona: sin esta columna,
-- un mensaje de prueba mandado al número de Meta que aparece en la bandeja no
-- se distingue de uno que entró por WAHA, y "creo que anduvo" no es una
-- prueba. Con ella, el panel dice "último mensaje por la API oficial: hace 2
-- minutos", que sí lo es.
alter table wa_inbox add column if not exists via text not null default 'waha'
  check (via in ('waha', 'cloud'));

create index if not exists idx_wa_inbox_via_created on wa_inbox (via, created_at desc);
