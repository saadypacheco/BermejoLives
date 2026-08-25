"use client";

import { useEffect, useMemo, useState } from "react";

/** URL temporal para previsualizar un File/Blob, liberada sola.
 *
 * POR QUÉ EXISTE
 * ==============
 *
 * `URL.createObjectURL(file)` crea un vínculo entre la página y el archivo, y
 * ese vínculo **ancla el archivo en memoria hasta que alguien lo suelta o se
 * cierra la pestaña**. No lo limpia el recolector de basura: aunque no quede
 * ninguna variable apuntando al File, el navegador tiene que poder resolver esa
 * URL, así que lo conserva.
 *
 * El agente carga un comercio, saca la foto, guarda, y el formulario se
 * limpia. Pero el `setPreview("")` sólo borra el string: la URL sigue viva y la
 * foto de 5 MB sigue ocupada. A los cincuenta comercios son 250 MB que ninguna
 * limpieza va a recuperar, y el celular de 4 GB dice "memoria insuficiente".
 *
 * Esto lo ata al ciclo de vida del componente: cambia el archivo, se revoca el
 * anterior; se desmonta, se revoca el último.
 *
 * OJO con la tentación de hacerlo inline en el render
 * (`<img src={URL.createObjectURL(x)} />`): eso crea una URL NUEVA en cada
 * render y no revoca ninguna. Es la misma fuga multiplicada por cuantas veces
 * React redibuje.
 */
export function useObjectUrl(file: Blob | null | undefined): string {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : ""), [file]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  return url;
}

/** La versión para listas: una URL por elemento, todas revocadas juntas. */
export function useObjectUrls<T>(items: T[], pick: (item: T) => Blob | null | undefined): string[] {
  const urls = useMemo(
    () => items.map((i) => { const b = pick(i); return b ? URL.createObjectURL(b) : ""; }),
    // `pick` se re-crea en cada render del padre; incluirla acá regeneraría las
    // URLs todo el tiempo, que es la fuga que este archivo viene a evitar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [items],
  );
  useEffect(() => () => urls.forEach((u) => u && URL.revokeObjectURL(u)), [urls]);
  return urls;
}

/** Para los casos fuera de React (o cuando el File se reemplaza a mano). */
export function useSwappableObjectUrl(): [string, (f: Blob | null) => void] {
  const [file, setFile] = useState<Blob | null>(null);
  return [useObjectUrl(file), setFile];
}
