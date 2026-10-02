"use client";

import { useEffect, useState } from "react";
import { Ic } from "@/components/ic";

const KEY = "uk-theme";

/** El tema de arranque para quien nunca eligió.
 *
 *  Era claro. URUKU se mira de noche y en la calle, casi siempre desde un
 *  celular: el mapa, las fotos de los locales y el verde de la marca se leen
 *  mejor sobre el fondo oscuro, y es lo que menos encandila cuando alguien
 *  abre el sitio parado en una vereda. El que prefiera claro lo cambia con el
 *  botón y se le recuerda. */
export const POR_DEFECTO: Tema = "dark";

type Tema = "light" | "dark";

/** Script inline: aplica el tema guardado antes del primer paint (evita parpadeo). */
export function ThemeNoFlash() {
  const js = `(function(){try{var t=localStorage.getItem('${KEY}')||'${POR_DEFECTO}';var r=document.getElementById('ukroot');if(r)r.setAttribute('data-theme',t);}catch(e){}})();`;
  return <script dangerouslySetInnerHTML={{ __html: js }} />;
}

/** Botón para alternar claro/oscuro. El usuario elige y se recuerda.
 * `iconOnly`: sin la palabra "Claro/Oscuro" (para la barra superior compacta). */
export function ThemeToggle({ iconOnly = false }: { iconOnly?: boolean }) {
  const [theme, setTheme] = useState<Tema>(POR_DEFECTO);

  useEffect(() => {
    const saved = (localStorage.getItem(KEY) as Tema) || POR_DEFECTO;
    setTheme(saved);
    document.getElementById("ukroot")?.setAttribute("data-theme", saved);
  }, []);

  const toggle = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem(KEY, next);
    document.getElementById("ukroot")?.setAttribute("data-theme", next);
  };

  return (
    <button className={`uk-theme-toggle${iconOnly ? " uk-theme-toggle-icon" : ""}`} onClick={toggle} aria-label="Cambiar color" title="Cambiar color">
      <Ic n={theme === "light" ? "luna" : "sol"} s={14} />
      {!iconOnly && (theme === "light" ? "Oscuro" : "Claro")}
    </button>
  );
}
