-- Las chalanas: un estado intermedio y su horario.
--
-- «operando | suspendidas» no alcanzaba: lo más común es que crucen pero
-- no como siempre —sólo de mañana por el río, cada tanto por poca gente—.
-- Y el horario de las chalanas cambia con la estación y el río; estaba
-- escrito en el saber local ("de día, cuando el río lo permite") y ahí no
-- lo cambia nadie a diario. Ahora es un campo que se carga en /contenido y
-- sale en la guía, en el home y en la Ayuda.
--
--   chalanas          operando | limitadas | suspendidas
--   chalanas_horario  texto libre: "7:00 a 18:00", "sólo de mañana"
alter table frontera_estado add column if not exists chalanas_horario text;
comment on column frontera_estado.chalanas is 'operando | limitadas | suspendidas';
comment on column frontera_estado.chalanas_horario is 'Horario de hoy de las chalanas, como lo carga la persona: "7:00 a 18:00", "sólo de mañana". NULL = no se cargó.';
