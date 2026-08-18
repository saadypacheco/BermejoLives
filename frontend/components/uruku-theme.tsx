"use client";

import { useEffect, useState } from "react";

const KEY = "uk-theme";

/** Script inline: aplica el tema guardado antes del primer paint (evita parpadeo). */
export function ThemeNoFlash() {
  const js = `(function(){try{var t=localStorage.getItem('${KEY}')||'light';var r=document.getElementById('ukroot');if(r)r.setAttribute('data-theme',t);}catch(e){}})();`;
  return <script dangerouslySetInnerHTML={{ __html: js }} />;
}

/** Botón para alternar claro/oscuro. El usuario elige y se recuerda.
 * `iconOnly`: sin la palabra "Claro/Oscuro" (para la barra superior compacta). */
export function ThemeToggle({ iconOnly = false }: { iconOnly?: boolean }) {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const saved = (localStorage.getItem(KEY) as "light" | "dark") || "light";
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
      {theme === "light" ? (
        <>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
          {!iconOnly && "Oscuro"}
        </>
      ) : (
        <>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
          {!iconOnly && "Claro"}
        </>
      )}
    </button>
  );
}
