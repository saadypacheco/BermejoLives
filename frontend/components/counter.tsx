"use client";

import { useEffect, useRef, useState } from "react";

export function Counter({ to, prefix = "" }: { to: number; prefix?: string }) {
  const [val, setVal] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const done = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !done.current) {
          done.current = true;
          const t0 = performance.now();
          const step = (now: number) => {
            const p = Math.min((now - t0) / 1400, 1);
            const eased = 1 - Math.pow(1 - p, 3);
            setVal(Math.floor(to * eased));
            if (p < 1) requestAnimationFrame(step);
            else setVal(to);
          };
          requestAnimationFrame(step);
        }
      },
      { threshold: 0.6 }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [to]);

  return (
    <span ref={ref}>
      {prefix}
      {val.toLocaleString("es-BO")}
    </span>
  );
}
