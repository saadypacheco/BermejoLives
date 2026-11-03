T = 33.0

def scene(name, t0, t1, fin=0.45, fout=0.45):
    dur = t1 - t0
    p1 = fin/dur*100; p2 = 100 - fout/dur*100
    return (f"@keyframes io_{name}{{0%{{opacity:0}}{p1:.2f}%{{opacity:1}}{p2:.2f}%{{opacity:1}}100%{{opacity:0}}}}\n"
            f".{name}{{animation:io_{name} {dur}s {t0}s linear both}}\n")

css_scenes = (scene('s1', 0, 5.0, 0.3, 0.45) + scene('s2', 4.6, 10.4) + scene('s3', 10.0, 15.9) +
              scene('s4', 15.5, 21.9) + scene('s5', 21.5, 27.4) + scene('s6', 27.0, T + 0.5, 0.5, 0.01))

def coin(name, x, y, t, fx, fy, size=180):
    return (f'<img class="coin" src="ic_{name}.png" style="left:{x-size/2}px;top:{y-size/2}px;width:{size}px;'
            f'--fx:{fx}px;--fy:{fy}px;animation-delay:{t}s,{t+0.9}s">')

def title(kicker, l1, l2, t, top=130):
    k = f'<div class="kick" style="animation-delay:{t}s">{kicker}</div>' if kicker else ''
    return (f'<div class="title" style="top:{top}px">{k}'
            f'<div class="tl1" style="animation-delay:{t+0.1}s">{l1}</div>'
            f'<div class="tl2" style="animation-delay:{t+0.3}s">{l2}</div></div>')

def sub(text, t, top=1730):
    return f'<div class="sub" style="top:{top}px;animation-delay:{t}s">{text}</div>'

def phone(t_in, t_scroll, cls=''):
    return (f'<div class="pw {cls}"><div class="phone" style="animation-delay:{t_in}s"><div class="scr"><div class="isl"></div>'
            f'<img class="strip" src="strip.jpg" style="animation-delay:{t_scroll}s"></div></div></div>')

WA = ('<svg viewBox="0 0 24 24" width="40" height="40"><path fill="#fff" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .1-3.2-.8-2.7-1.1-4.4-3.9-4.5-4.1-.1-.2-1.1-1.4-1.1-2.7s.7-1.9.9-2.2c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.9-1c.2-.3.4-.2.7-.1l1.9.9c.3.1.5.2.5.3.1.2.1.6-.2 1.2z"/></svg>')

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;background:#08110C}}
.stage{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#08110C}}
.sc{{position:absolute;inset:0;overflow:hidden}}
{css_scenes}
.bg{{position:absolute;inset:0;background:radial-gradient(110% 75% at 50% 58%,#0F3423 0%,#0B1E15 45%,#08110C 100%)}}
.glow{{position:absolute;left:540px;top:1100px;width:1200px;height:1200px;margin:-600px 0 0 -600px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(38,185,105,.55),rgba(29,141,82,.25) 48%,transparent 74%);filter:blur(24px)}}
.title{{position:absolute;left:0;right:0;text-align:center;padding:0 60px}}
.kick{{display:inline-block;font-weight:600;font-size:28px;letter-spacing:3px;color:#04311A;background:#34D27F;border-radius:30px;padding:8px 22px;margin-bottom:22px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
.tl1,.tl2{{font-weight:600;font-size:76px;line-height:1.08;letter-spacing:-2px;color:#fff;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
.tl2{{color:#34D27F}}
.sub{{position:absolute;left:0;right:0;text-align:center;font-size:36px;line-height:1.4;color:#D2E2D8;padding:0 100px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
@keyframes rise{{from{{opacity:0;transform:translateY(36px)}}to{{opacity:1;transform:none}}}}
@keyframes pop{{from{{opacity:0;transform:translate(var(--fx,0),var(--fy,0)) scale(.4)}}to{{opacity:1;transform:rotate(var(--r,0deg))}}}}
@keyframes bob{{0%,100%{{translate:0 0}}50%{{translate:0 -12px}}}}
.coin{{position:absolute;filter:drop-shadow(0 24px 30px rgba(0,0,0,.6));animation:cpop .9s cubic-bezier(.2,1.35,.3,1) both, bob 3s ease-in-out infinite}}
@keyframes cpop{{from{{opacity:0;transform:translate(var(--fx),var(--fy)) scale(.15) rotate(-40deg)}}to{{opacity:1;transform:none}}}}
.card{{position:absolute;overflow:hidden;box-shadow:0 34px 70px rgba(0,0,0,.55),0 0 0 1.5px rgba(80,220,140,.25),0 0 60px rgba(52,210,127,.2);
 animation:pop .9s cubic-bezier(.2,1.25,.3,1) both, bob 3.2s ease-in-out infinite}}
.card img{{display:block;width:100%}}
.panel{{position:absolute;background:#16211B;border:2px solid #2B4A39;border-radius:40px;box-shadow:0 34px 70px rgba(0,0,0,.55),0 0 60px rgba(52,210,127,.18);
 animation:pop .9s cubic-bezier(.2,1.25,.3,1) both, bob 3.4s ease-in-out infinite}}

/* phone */
.pw{{position:absolute;left:540px;top:600px;width:540px;height:1100px;margin-left:-270px;perspective:2200px;transform:scale(.88);transform-origin:50% 0}}
.phone{{width:540px;height:1100px;border-radius:80px;background:#0d0d0d;padding:15px;transform:rotateX(12deg) rotateY(-16deg) rotateZ(4deg);
 box-shadow:0 70px 140px rgba(0,0,0,.65),inset 0 0 0 3px #2c2c2c,0 0 0 2px #444;animation:phIn 1.1s cubic-bezier(.16,.84,.2,1) both}}
@keyframes phIn{{from{{opacity:0;transform:translateY(260px) rotateX(30deg) rotateY(-36deg) rotateZ(8deg) scale(.85)}}}}
.scr{{width:510px;height:1070px;border-radius:66px;overflow:hidden;position:relative;background:#111A16}}
.isl{{position:absolute;top:18px;left:50%;margin-left:-70px;width:140px;height:40px;border-radius:24px;background:#000;z-index:3}}
.scr .strip{{display:block;width:510px;margin-top:70px;animation:scroll 4s cubic-bezier(.45,0,.3,1) both}}
@keyframes scroll{{from{{transform:translateY(0)}}to{{transform:translateY(-420px)}}}}

/* S1 */
.mapbig{{position:absolute;left:80px;top:640px;width:920px;border-radius:44px;overflow:hidden;box-shadow:0 50px 100px rgba(0,0,0,.6),0 0 0 2px rgba(80,220,140,.25);
 transform:perspective(1800px) rotateX(24deg) rotateZ(-4deg);animation:rise 1s .5s cubic-bezier(.2,.8,.2,1) both}}
.mapbig img{{display:block;width:100%}}
.mapbig:after{{content:"";position:absolute;inset:0;background:linear-gradient(#08110C00 40%,#08110Cee)}}
.pin{{position:absolute;width:var(--s);height:calc(var(--s)*1.3);animation:drop .8s cubic-bezier(.3,1.5,.5,1) both}}
.pin .b{{position:absolute;inset:0 0 auto 0;height:var(--s);border-radius:50% 50% 50% 0;transform:rotate(-45deg);
 background:radial-gradient(circle at 30% 30%,#A6F7CB 0%,#3DD68C 25%,#1D8D52 62%,#0B4D2B 100%);
 box-shadow:inset -8px -10px 18px rgba(0,0,0,.35),inset 6px 8px 14px rgba(255,255,255,.35),0 20px 40px rgba(0,0,0,.45),0 0 40px rgba(61,214,140,.5)}}
.pin .h{{position:absolute;left:50%;top:calc(var(--s)*.5);width:calc(var(--s)*.38);height:calc(var(--s)*.38);transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle at 35% 35%,#fff,#DCEFE4)}}
.pin.big .b{{background:radial-gradient(circle at 30% 30%,#FFB3A6 0%,#F0524A 25%,#C21F25 62%,#6E0D10 100%);box-shadow:inset -8px -10px 18px rgba(0,0,0,.35),inset 6px 8px 14px rgba(255,255,255,.35),0 20px 40px rgba(0,0,0,.45),0 0 50px rgba(240,82,74,.6)}}
@keyframes drop{{from{{opacity:0;transform:translateY(-300px)}}to{{opacity:1;transform:none}}}}
.tag1{{position:absolute;left:560px;top:930px;font-weight:600;font-size:34px;color:#fff;background:#16211B;border:2px solid #F0524A;border-radius:30px;padding:12px 26px;
 box-shadow:0 20px 40px rgba(0,0,0,.5);animation:rise .6s 2.9s cubic-bezier(.2,.8,.2,1) both}}

/* S3 chat */
.chat{{left:70px;top:640px;width:940px;padding:0 0 34px;overflow:hidden;--fy:120px;animation-delay:10.6s,11.5s}}
.chead{{display:flex;align-items:center;gap:20px;padding:26px 34px;background:#1F2C25;border-bottom:1px solid #2B4A39}}
.av{{width:72px;height:72px;border-radius:50%;background:url(prod.jpg) center/cover;border:2px solid #34D27F}}
.cn{{font-weight:600;font-size:34px;color:#fff}} .cs{{font-size:24px;color:#8FA79A}}
.bub{{max-width:700px;font-size:34px;line-height:1.35;padding:20px 28px;border-radius:28px;margin:26px 34px 0;animation:rise .5s cubic-bezier(.2,.8,.2,1) both}}
.in{{background:#24332B;color:#fff;border-top-left-radius:6px}}
.out{{background:#1F9D58;color:#fff;margin-left:auto;border-top-right-radius:6px}}
.bub small{{display:block;font-size:22px;color:#A8BDB1;text-align:right;margin-top:6px}}
.out small{{color:#D8F5E5}}
.typing{{display:inline-flex;gap:10px;padding:24px 28px}}
.typing i{{width:14px;height:14px;border-radius:50%;background:#8FA79A;animation:dot 1s infinite}}
.typing i:nth-child(2){{animation-delay:.15s}}.typing i:nth-child(3){{animation-delay:.3s}}
@keyframes dot{{50%{{transform:translateY(-8px);opacity:.5}}}}
.chips{{position:absolute;left:0;right:0;top:1230px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;padding:0 60px}}
.chip{{font-size:32px;font-weight:600;color:#fff;background:#16211B;border:2px solid #2B4A39;border-radius:40px;padding:14px 28px;display:flex;align-items:center;gap:14px;
 box-shadow:0 20px 40px rgba(0,0,0,.45);animation:rise .6s cubic-bezier(.2,.8,.2,1) both}}
.chip i{{width:16px;height:16px;border-radius:50%;background:#34D27F;box-shadow:0 0 14px #34D27F}}

/* S4 */
.send{{left:90px;top:600px;width:560px;padding:22px;--fx:-100px;--fy:80px;--r:-3deg;animation-delay:16.0s,16.9s;background:#1F9D58;border-color:#34D27F}}
.send .ph{{width:100%;height:420px;border-radius:24px;background:url(prod.jpg) center/cover}}
.send .tx{{font-size:40px;font-weight:600;color:#fff;padding:18px 8px 0}}
.send small{{display:block;font-size:24px;color:#D8F5E5;text-align:right}}
.arrow{{position:absolute;left:500px;top:1120px;width:150px;height:150px;animation:rise .6s 17.6s both}}
.offer{{left:400px;top:1150px;width:600px;padding:22px;--fx:-200px;--fy:-300px;--r:2deg;animation-delay:18.0s,18.9s}}
.offer .row{{display:flex;gap:24px;align-items:center}}
.offer .ph{{width:190px;height:190px;border-radius:24px;background:url(prod.jpg) center/cover;flex:none}}
.badge{{display:inline-block;font-weight:700;font-size:26px;color:#fff;background:#E5484D;border-radius:14px;padding:4px 14px}}
.price{{font-weight:700;font-size:64px;color:#fff;line-height:1.1;margin-top:6px}}
.ot{{font-size:28px;color:#A8BDB1}}
.obtn{{display:flex;gap:16px;margin-top:20px}}
.obtn span{{flex:1;text-align:center;font-weight:700;font-size:28px;border-radius:18px;padding:16px 0}}
.b1{{background:#1F9D58;color:#fff}}.b2{{background:#24332B;color:#fff;border:2px solid #2B4A39}}

/* S5 dashboard */
.dash{{left:70px;top:560px;width:940px;padding:40px;--fy:150px;animation-delay:22.0s,22.9s}}
.dt{{display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:36px;color:#fff;margin-bottom:30px}}
.ej{{font-size:22px;font-weight:600;color:#8FA79A;border:1.5px solid #3A5847;border-radius:14px;padding:4px 12px}}
.kpis{{display:flex;gap:24px}}
.kpi{{flex:1;background:#1E2B24;border-radius:28px;padding:26px}}
.kl{{font-size:26px;color:#A8BDB1}}
.kv{{font-weight:700;font-size:80px;color:#fff;line-height:1.1;font-variant-numeric:tabular-nums}}
.kv em{{font-style:normal;color:#34D27F}}
.ks{{font-size:22px;color:#6F8A7B}}
.bars{{display:flex;align-items:flex-end;gap:16px;height:220px;margin-top:34px;padding:0 6px;border-bottom:2px solid #2B4A39}}
.bar{{flex:1;border-radius:12px 12px 0 0;background:linear-gradient(#34D27F,#1D8D52);transform-origin:bottom;animation:grow .7s cubic-bezier(.2,.9,.3,1) both}}
.bar.dim{{background:linear-gradient(#2E6B4A,#1C4430)}}
@keyframes grow{{from{{transform:scaleY(0)}}}}
.days{{display:flex;gap:16px;padding:10px 6px 0}}
.days span{{flex:1;text-align:center;font-size:22px;color:#6F8A7B}}
.words{{margin-top:34px}}
.wl{{font-size:26px;color:#A8BDB1;margin-bottom:14px}}
.wrow{{display:flex;gap:14px;flex-wrap:wrap}}
.w{{font-size:28px;font-weight:600;color:#C9F5DC;background:#1E3A2B;border-radius:20px;padding:10px 20px;animation:rise .5s both}}

/* S6 */
.benefits{{position:absolute;left:90px;right:90px;top:560px;display:flex;flex-direction:column;gap:22px}}
.bf{{display:flex;align-items:center;gap:26px;background:#16211B;border:2px solid #2B4A39;border-radius:32px;padding:22px 30px;
 box-shadow:0 20px 40px rgba(0,0,0,.4);animation:slide .6s cubic-bezier(.2,.9,.3,1) both}}
@keyframes slide{{from{{opacity:0;transform:translateX(-80px)}}}}
.bf .ck{{width:56px;height:56px;border-radius:50%;background:#34D27F;display:grid;place-items:center;flex:none;box-shadow:0 0 24px rgba(52,210,127,.6)}}
.bf b{{font-weight:600;font-size:36px;color:#fff}}
.logo6{{position:absolute;left:290px;top:1090px;width:500px;animation:rise .8s 30.0s cubic-bezier(.2,.8,.2,1) both}}
.cta{{position:absolute;left:0;right:0;top:1290px;text-align:center;animation:rise .7s 30.4s cubic-bezier(.2,.8,.2,1) both}}
.cta .u{{font-weight:700;font-size:72px;color:#34D27F;line-height:1.1}}
.cta .w2{{display:inline-flex;align-items:center;gap:14px;margin-top:20px;font-weight:600;font-size:38px;color:#fff;background:#1F9D58;border-radius:40px;padding:14px 32px}}
.lema{{position:absolute;left:0;right:0;top:1560px;text-align:center;font-size:32px;color:#A8BDB1;animation:rise .7s 30.9s both}}
</style></head><body><div class="stage"><img src="prod.jpg" style="display:none">

<!-- S1 hook -->
<div class="sc s1"><div class="bg"></div><div class="glow" style="top:1150px"></div>
 {title('PARA COMERCIOS', '¿Tiene un negocio?', 'Póngalo en el mapa.', 0.2, 150)}
 <div class="mapbig"><img src="f_mapa.jpg"></div>
 <div class="pin" style="--s:60px;left:240px;top:1010px;animation-delay:1.3s"><div class="b"></div><div class="h"></div></div>
 <div class="pin" style="--s:52px;left:790px;top:1120px;animation-delay:1.5s"><div class="b"></div><div class="h"></div></div>
 <div class="pin" style="--s:56px;left:350px;top:1290px;animation-delay:1.7s"><div class="b"></div><div class="h"></div></div>
 <div class="pin" style="--s:48px;left:700px;top:1360px;animation-delay:1.9s"><div class="b"></div><div class="h"></div></div>
 <div class="pin big" style="--s:110px;left:460px;top:900px;animation-delay:2.4s"><div class="b"></div><div class="h"></div></div>
 <div class="tag1">Su negocio</div>
 {sub('Uruku es la guía de comercios y servicios de Bolivia.', 3.2, 1650)}
</div>

<!-- S2 beneficio 1 -->
<div class="sc s2"><div class="bg"></div><div class="glow"></div>
 {title('BENEFICIO 1', 'Aparezca donde', 'la gente busca', 4.9, 130)}
 {phone(5.2, 6.3)}
 <div class="card" style="left:40px;top:1300px;width:1000px;border-radius:44px;--fy:-250px;--r:-1.5deg;animation-delay:7.4s,8.3s"><img src="f_card.png"></div>
 {coin('pin', 150, 760, 6.0, 390, 300)}{coin('tienda', 930, 740, 6.4, -390, 300)}
 {sub('En el mapa y en el buscador, con fotos, horario y ubicación.', 8.2, 1690)}
</div>

<!-- S3 beneficio 2 -->
<div class="sc s3"><div class="bg"></div><div class="glow" style="top:1000px"></div>
 {title('BENEFICIO 2', 'Le escriben directo', 'a su WhatsApp', 10.3, 130)}
 <div class="panel chat">
  <div class="chead"><div class="av"></div><div><div class="cn">Anteojos de sol</div><div class="cs">en línea</div></div></div>
  <div class="bub in" style="animation-delay:11.4s">Hola, lo encontré en Uruku. ¿Tiene lentes de sol polarizados?<small>18:42</small></div>
  <div class="bub out" style="animation-delay:12.6s">¡Sí! Tenemos varios modelos. Lo esperamos.<small>18:43 ✓✓</small></div>
 </div>
 {coin('whatsapp', 900, 600, 11.2, -200, 200, 190)}
 <div class="chips"><div class="chip" style="animation-delay:13.4s"><i></i>Sin intermediarios</div><div class="chip" style="animation-delay:13.7s"><i></i>0% comisión por venta</div></div>
</div>

<!-- S4 beneficio 3 -->
<div class="sc s4"><div class="bg"></div><div class="glow" style="top:1050px"></div>
 {title('BENEFICIO 3', 'Publique ofertas', 'con una foto', 15.8, 130)}
 <div class="panel send"><div class="ph"></div><div class="tx">Lentes de sol · 80 Bs</div><small>Enviado a Uruku ✓✓</small></div>
 <svg class="arrow" viewBox="0 0 100 100"><path d="M20 10 C 30 60, 60 70, 85 80" stroke="#34D27F" stroke-width="6" fill="none" stroke-linecap="round" stroke-dasharray="6 12"/><path d="M70 88 L88 81 L80 64" stroke="#34D27F" stroke-width="6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
 <div class="panel offer"><div class="row"><div class="ph"></div><div><span class="badge">¡Oferta!</span><div class="price">80 Bs</div><div class="ot">Lentes de sol</div></div></div>
  <div class="obtn"><span class="b1">Reservar</span><span class="b2">Consultar</span></div></div>
 {coin('camara', 860, 640, 16.6, -250, 150, 170)}{coin('oferta', 170, 1500, 18.6, 300, -250, 170)}
 {sub('Se la manda por WhatsApp y aparece en las ofertas del día.', 19.4, 1730)}
</div>

<!-- S5 beneficio 4 -->
<div class="sc s5"><div class="bg"></div><div class="glow" style="top:1150px"></div>
 {title('BENEFICIO 4', 'Vea cuántos', 'lo encuentran', 21.8, 130)}
 <div class="panel dash">
  <div class="dt">Su negocio · últimos 30 días<span class="ej">Ejemplo</span></div>
  <div class="kpis">
   <div class="kpi"><div class="kl">Visitas a su ficha</div><div class="kv" id="n1">0</div><div class="ks">personas vieron su negocio</div></div>
   <div class="kpi"><div class="kl">Contactos</div><div class="kv"><em id="n2">0</em></div><div class="ks">por WhatsApp y «Cómo llegar»</div></div>
  </div>
  <div class="bars">{''.join(f'<div class="bar {"dim" if i<4 else ""}" style="height:{h}%;animation-delay:{23.0+i*0.08:.2f}s"></div>' for i,h in enumerate([30,42,38,55,61,74,92]))}</div>
  <div class="days"><span>Lun</span><span>Mar</span><span>Mié</span><span>Jue</span><span>Vie</span><span>Sáb</span><span>Dom</span></div>
  <div class="words"><div class="wl">Con qué lo buscan</div><div class="wrow">
   <span class="w" style="animation-delay:24.0s">lentes de sol</span><span class="w" style="animation-delay:24.2s">anteojos</span><span class="w" style="animation-delay:24.4s">armazón</span><span class="w" style="animation-delay:24.6s">óptica</span></div></div>
 </div>
 {coin('grafico', 150, 1640, 23.4, 200, -300, 170)}{coin('estrella', 930, 1640, 23.8, -200, -300, 170)}
</div>

<!-- S6 cierre -->
<div class="sc s6"><div class="bg"></div><div class="glow" style="top:900px"></div>
 {title(None, 'Sume su negocio', 'a Uruku', 27.2, 210)}
 <div class="benefits">
  <div class="bf" style="animation-delay:27.9s"><div class="ck"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10" stroke="#04311A" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></div><b>Gratis para empezar</b></div>
  <div class="bf" style="animation-delay:28.3s"><div class="ck"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10" stroke="#04311A" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></div><b>Sin comisiones por venta</b></div>
  <div class="bf" style="animation-delay:28.7s"><div class="ck"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10" stroke="#04311A" stroke-width="3.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></div><b>Todo desde su WhatsApp</b></div>
 </div>
 <img class="logo6" src="logo.png">
 <div class="cta"><div class="u">uruku.bo</div><div class="w2">{WA} 67 671 888</div></div>
 <div class="lema">Si está en Bolivia, está en Uruku.</div>
</div>

</div>
<script>
// counters driven by animation time of a dummy animation
const d=document.createElement('div');document.body.appendChild(d);
const a=d.animate([{{opacity:0}},{{opacity:1}}],{{duration:{T*1000},fill:'both'}});
function upd(){{const t=(a.currentTime||0)/1000;const p=Math.min(1,Math.max(0,(t-22.6)/1.6));const e=1-Math.pow(1-p,3);
 document.getElementById('n1').textContent=Math.round(1240*e).toLocaleString('es');document.getElementById('n2').textContent=Math.round(186*e);}}
window.__upd=upd;
</script>
</body></html>'''
open('comercios.html', 'w').write(html)
print('ok')
