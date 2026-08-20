-- Código de identificación del comercio (ver backend/app/core/codigo.py).
--
-- Se genera en el alta y se le deja al comercio en papel. Con eso puede mandar
-- ofertas por WhatsApp desde CUALQUIER número — sin número propio cargado, sin
-- login y sin haber pagado — y la publicación se atribuye a su local.
--
-- Es además el identificador estable de cara al dueño: el celular puede cambiar,
-- el código no.
--
-- 4 caracteres de un alfabeto de 31 (sin 0/O/1/I/L, que se confunden al
-- dictarlos): ~923.000 combinaciones. No es secreto ni hace falta que lo sea:
-- todo lo que entra por WhatsApp pasa por moderación humana, así que un código
-- equivocado no publica nada.

alter table comercios add column if not exists codigo text;

-- En qué se apoyó la atribución de cada publicación. Lo usa el panel para
-- mostrarlo y para validar el código antes de aprobar.
alter table publicaciones add column if not exists codigo_recibido text;
alter table publicaciones add column if not exists identidad_origen text;

-- Backfill: los comercios que ya existen también necesitan su código.
do $$
declare
  alfabeto constant text := '23456789ABCDEFGHJKMNPQRSTUVWXYZ';
  c        record;
  intento  text;
  i        int;
  reintentos int;
begin
  for c in select id from comercios where codigo is null loop
    reintentos := 0;
    loop
      intento := '';
      for i in 1..4 loop
        intento := intento || substr(alfabeto, 1 + floor(random() * length(alfabeto))::int, 1);
      end loop;
      exit when not exists (select 1 from comercios where codigo = intento);
      reintentos := reintentos + 1;
      if reintentos > 50 then
        raise exception 'No se pudo generar un código único para el comercio %', c.id;
      end if;
    end loop;
    update comercios set codigo = intento where id = c.id;
  end loop;
end $$;

-- Único, pero tolerando NULL por si alguna fila queda sin código.
create unique index if not exists idx_comercios_codigo
  on comercios (codigo) where codigo is not null;
