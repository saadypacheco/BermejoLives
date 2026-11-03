import json, numpy as np

q = json.load(open('quad.json'))
# expand quad slightly outward from its center so content covers edges
cx = np.mean([v[0] for v in q.values()]); cy = np.mean([v[1] for v in q.values()])
def ex(p, k=1.02): return [cx + (p[0]-cx)*k, cy + (p[1]-cy)*k]
dst = [ex(q['TL']), ex(q['TR']), ex(q['BR']), ex(q['BL'])]
W, H = 500, 1220
src = [[0, 0], [W, 0], [W, H], [0, H]]
A = []; B = []
for (x, y), (u, v) in zip(src, dst):
    A.append([x, y, 1, 0, 0, 0, -u*x, -u*y]); B.append(u)
    A.append([0, 0, 0, x, y, 1, -v*x, -v*y]); B.append(v)
h = np.linalg.solve(np.array(A, float), np.array(B, float))
a, b, c, d, e, f, g, i = h
M = f"matrix3d({a},{d},0,{g},{b},{e},0,{i},0,0,1,0,{c},{f},0,1)"

T = 31.5  # total seconds
def scene(name, t0, t1, fin=0.45, fout=0.45):
    dur = t1 - t0
    p1 = fin/dur*100; p2 = 100 - fout/dur*100
    return (f"@keyframes io_{name}{{0%{{opacity:0}}{p1:.2f}%{{opacity:1}}{p2:.2f}%{{opacity:1}}100%{{opacity:0}}}}\n"
            f".{name}{{animation:io_{name} {dur}s {t0}s linear both}}\n")

css_scenes = (scene('s1', 0, 4.8, 0.3, 0.5) + scene('s2', 4.4, 10.5) + scene('s34', 10.2, 21.7) +
              scene('s5', 21.4, 27.3) + scene('s6', 27.0, T + 0.5, 0.5, 0.01))

def coin(name, x, y, t, fx, fy, size=190, cls=''):
    # x,y = final center; fx,fy = start offset (from screen/card) relative to final
    return (f'<img class="coin {cls}" src="ic_{name}.png" style="left:{x-size/2}px;top:{y-size/2}px;width:{size}px;'
            f'--fx:{fx}px;--fy:{fy}px;animation-delay:{t}s,{t+0.9}s">')

def title(kicker, l1, l2, t, top=130, cls=''):
    k = f'<div class="kick" style="animation-delay:{t}s">{kicker}</div>' if kicker else ''
    return (f'<div class="title {cls}" style="top:{top}px">{k}'
            f'<div class="tl1" style="animation-delay:{t+0.1}s">{l1}</div>'
            f'<div class="tl2" style="animation-delay:{t+0.3}s">{l2}</div></div>')

# coins in hands scene: start at screen center (approx 540,930)
sc = (540, 930)
def cs(name, x, y, t): return coin(name, x, y, t, sc[0]-x, sc[1]-y)

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;background:#08110C}}
.stage{{position:relative;width:1080px;height:1920px;overflow:hidden;background:#08110C}}
.sc{{position:absolute;inset:0;overflow:hidden}}
{css_scenes}
/* type */
.title{{position:absolute;left:0;right:0;text-align:center;padding:0 70px}}
.kick{{display:inline-block;font-weight:600;font-size:28px;letter-spacing:3px;color:#04311A;background:#34D27F;border-radius:30px;padding:8px 22px;margin-bottom:22px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
.tl1,.tl2{{font-weight:600;font-size:78px;line-height:1.08;letter-spacing:-2px;color:#fff;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
.tl2{{color:#34D27F}}
.sub{{position:absolute;left:0;right:0;text-align:center;font-size:34px;line-height:1.4;color:#D2E2D8;padding:0 110px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}}
@keyframes rise{{from{{opacity:0;transform:translateY(36px)}}to{{opacity:1;transform:none}}}}
.shade-top{{position:absolute;left:0;right:0;top:0;height:760px;background:linear-gradient(#08110Cf2,#08110Ca0 55%,transparent)}}
.shade-bot{{position:absolute;left:0;right:0;bottom:0;height:520px;background:linear-gradient(transparent,#08110Cd8 60%,#08110C)}}

/* S1 */
.kb1{{position:absolute;inset:0;background:url(chico.png) center/cover;transform-origin:66% 63%;animation:kb1 4.8s 0s cubic-bezier(.4,0,.7,1) both}}
@keyframes kb1{{0%{{transform:scale(1.04)}}75%{{transform:scale(1.18)}}100%{{transform:scale(1.9)}}}}

/* S2 */
.kb2{{position:absolute;inset:0;transform-origin:50% 48%;animation:kb2 6.1s 4.4s ease-out both}}
@keyframes kb2{{from{{transform:scale(1.18)}}to{{transform:scale(1)}}}}
.screen{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;transform-origin:0 0;transform:{M};overflow:hidden;background:#111A16}}
.screen .strip{{display:block;width:{W}px;animation:scroll2 4.6s 5.6s cubic-bezier(.45,0,.3,1) both}}
@keyframes scroll2{{from{{transform:translateY(0)}}to{{transform:translateY(-560px)}}}}
.hands{{position:absolute;inset:0;width:1080px;height:1920px}}
.glow2{{position:absolute;left:540px;top:930px;width:1100px;height:1100px;margin:-550px 0 0 -550px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(38,185,105,.45),transparent 70%);filter:blur(30px)}}

/* coins */
.coin{{position:absolute;filter:drop-shadow(0 24px 30px rgba(0,0,0,.6));animation:cpop .9s cubic-bezier(.2,1.35,.3,1) both, cbob 3s ease-in-out infinite}}
@keyframes cpop{{from{{opacity:0;transform:translate(var(--fx),var(--fy)) scale(.15) rotate(-40deg)}}to{{opacity:1;transform:none}}}}
@keyframes cbob{{0%,100%{{translate:0 0}}50%{{translate:0 -12px}}}}

/* S3/S4 shared bg */
.bg{{position:absolute;inset:0;background:radial-gradient(110% 75% at 50% 58%,#0F3423 0%,#0B1E15 45%,#08110C 100%)}}
.glow{{position:absolute;left:540px;top:1160px;width:1200px;height:1200px;margin:-600px 0 0 -600px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(38,185,105,.55),rgba(29,141,82,.25) 48%,transparent 74%);filter:blur(24px)}}
.pw{{position:absolute;left:540px;top:640px;width:540px;height:1100px;margin-left:-270px;perspective:2200px;transform:scale(.9);transform-origin:50% 0;
 animation:pwOut .7s 16.0s ease-in both}}
@keyframes pwOut{{to{{opacity:.28;transform:scale(.84) translateY(40px);filter:blur(3px)}}}}
.phone{{width:540px;height:1100px;border-radius:80px;background:#0d0d0d;padding:15px;transform:rotateX(12deg) rotateY(-16deg) rotateZ(4deg);
 box-shadow:0 70px 140px rgba(0,0,0,.65),inset 0 0 0 3px #2c2c2c,0 0 0 2px #444;animation:phIn 1.1s 10.2s cubic-bezier(.16,.84,.2,1) both}}
@keyframes phIn{{from{{opacity:0;transform:translateY(260px) rotateX(30deg) rotateY(-36deg) rotateZ(8deg) scale(.85)}}}}
.scr{{width:510px;height:1070px;border-radius:66px;overflow:hidden;position:relative;background:#111A16}}
.isl{{position:absolute;top:18px;left:50%;margin-left:-70px;width:140px;height:40px;border-radius:24px;background:#000;z-index:3}}
.scr .strip{{display:block;width:510px;margin-top:70px;animation:scroll3 1.6s 12.7s cubic-bezier(.45,0,.3,1) both}}
@keyframes scroll3{{from{{transform:translateY(0)}}to{{transform:translateY(-300px)}}}}

/* search pill */
.search{{position:absolute;left:60px;right:60px;top:500px;height:120px;border-radius:30px;background:#16211B;border:2px solid #2B4A39;
 display:flex;align-items:center;padding-left:34px;gap:22px;box-shadow:0 30px 60px rgba(0,0,0,.55),0 0 50px rgba(52,210,127,.22);
 animation:rise .7s 10.7s cubic-bezier(.2,.8,.2,1) both, sOut .5s 15.6s ease-in both}}
@keyframes sOut{{to{{opacity:0;transform:translateY(-30px)}}}}
.search .mag{{width:38px;height:38px;border:4px solid #8FA79A;border-radius:50%;position:relative;flex:none}}
.search .mag:after{{content:"";position:absolute;width:4px;height:16px;background:#8FA79A;right:-9px;bottom:-12px;transform:rotate(-45deg);border-radius:2px}}
.typed{{font-size:44px;color:#fff;font-weight:500;white-space:nowrap;overflow:hidden;width:0;animation:type 1s 11.3s steps(6) both}}
@keyframes type{{to{{width:150px}}}}
.caret{{width:4px;height:52px;background:#34D27F;animation:blink .8s 10.7s steps(2) 6 both}}
@keyframes blink{{50%{{opacity:0}}}}
.btn{{margin-left:auto;height:100%;padding:0 46px;display:grid;place-items:center;font-weight:700;font-size:38px;color:#fff;background:#1F9D58;border-radius:0 28px 28px 0;
 animation:press .35s 12.4s ease-in-out both}}
@keyframes press{{50%{{transform:scale(.92);filter:brightness(1.25)}}}}

/* floating cards */
.card{{position:absolute;overflow:hidden;box-shadow:0 34px 70px rgba(0,0,0,.55),0 0 0 1.5px rgba(80,220,140,.25),0 0 60px rgba(52,210,127,.2)}}
.card img{{display:block;width:100%}}
.pop{{animation:pop .9s cubic-bezier(.2,1.25,.3,1) both, cbob 3.2s ease-in-out infinite}}
@keyframes pop{{from{{opacity:0;transform:translate(var(--fx),var(--fy)) scale(.4)}}to{{opacity:1;transform:rotate(var(--r,0deg))}}}}
.econ{{left:50px;top:1210px;width:980px;border-radius:44px;--fx:0px;--fy:-200px;--r:-1.5deg;animation-delay:13.4s,14.3s;
 animation-name:pop,cbob,econMove;animation-duration:.9s,3.2s,.9s;animation-iteration-count:1,infinite,1;animation-delay:13.4s,14.3s,16.0s;animation-timing-function:cubic-bezier(.2,1.25,.3,1),ease-in-out,cubic-bezier(.3,.9,.3,1);animation-fill-mode:both,none,both}}
@keyframes econMove{{to{{top:820px}}}}
.chips{{position:absolute;left:0;right:0;top:1300px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;padding:0 60px}}
.chip{{font-size:32px;font-weight:600;color:#fff;background:#16211B;border:2px solid #2B4A39;border-radius:40px;padding:14px 28px;display:flex;align-items:center;gap:14px;
 box-shadow:0 20px 40px rgba(0,0,0,.45);animation:rise .6s cubic-bezier(.2,.8,.2,1) both}}
.chip i{{width:16px;height:16px;border-radius:50%;background:#34D27F;box-shadow:0 0 14px #34D27F}}

/* S5 */
.mapc{{position:absolute;left:190px;top:560px;width:700px;border-radius:40px;overflow:hidden;box-shadow:0 40px 80px rgba(0,0,0,.6),0 0 0 2px rgba(80,220,140,.25);
 transform:perspective(1600px) rotateX(18deg) rotateZ(-3deg);animation:rise .8s 21.6s cubic-bezier(.2,.8,.2,1) both}}
.mapc img{{display:block;width:100%}}
.mapc:after{{content:"";position:absolute;inset:0;background:linear-gradient(transparent 55%,#08110C)}}
.farm{{left:40px;top:1240px;width:1000px;border-radius:34px;--fx:0px;--fy:-300px;--r:-1deg;animation-delay:22.3s,23.2s}}
.camb{{left:470px;top:1420px;width:560px;border-radius:40px;--fx:-100px;--fy:-400px;--r:2deg;animation-delay:22.9s,23.8s}}

/* S6 */
.logo6{{position:absolute;left:190px;top:700px;width:700px;animation:logoIn 1s 27.3s cubic-bezier(.2,1.2,.3,1) both}}
@keyframes logoIn{{from{{opacity:0;transform:scale(.7)}}}}
.url6{{position:absolute;left:0;right:0;top:1060px;text-align:center;font-weight:700;font-size:96px;color:#34D27F;letter-spacing:-1px;animation:rise .7s 27.9s cubic-bezier(.2,.8,.2,1) both}}
.nodl{{position:absolute;left:0;right:0;top:1210px;display:flex;justify-content:center;animation:rise .7s 28.3s cubic-bezier(.2,.8,.2,1) both}}
.nodl span{{font-size:34px;font-weight:600;color:#04311A;background:#34D27F;border-radius:40px;padding:12px 30px}}
.lema{{position:absolute;left:0;right:0;top:1330px;text-align:center;font-size:42px;color:#fff;animation:rise .7s 28.7s cubic-bezier(.2,.8,.2,1) both}}
</style></head><body><div class="stage"><img src="chico.png" style="display:none">

<!-- S1 -->
<div class="sc s1"><div class="kb1"></div><div class="shade-top"></div>
{title(None, 'Primera vez', 'en Santa Cruz.', 0.3, 150)}
<div class="sub" style="top:470px;animation-delay:1.2s;font-size:46px;font-weight:600;color:#fff">¿Por dónde empiezo?</div>
</div>

<!-- S2 -->
<div class="sc s2"><div class="kb2"><div class="glow2"></div>
 <div class="screen"><img class="strip" src="strip.jpg"></div>
 <img class="hands" src="manos_key.png"></div>
 <div class="shade-top" style="height:420px"></div>
 {title(None, 'Toda la ciudad', 'en su celular', 4.9, 110)}
 {cs('pin', 150, 560, 6.2)}{cs('comida', 935, 520, 6.7)}{cs('farm', 125, 1000, 7.2)}
 {cs('cajero', 960, 980, 7.7)}{cs('whatsapp', 175, 1440, 8.2)}{cs('cambio', 930, 1430, 8.7)}
 <div class="shade-bot" style="height:360px"></div>
 <div class="sub" style="top:1700px;animation-delay:5.6s">Comercios, servicios y datos útiles, en uruku.bo</div>
</div>

<!-- S3 + S4 -->
<div class="sc s34"><div class="bg"></div><div class="glow"></div>
 <div class="pw"><div class="phone"><div class="scr"><div class="isl"></div><img class="strip" src="strip.jpg"></div></div></div>
 <div style="position:absolute;inset:0;animation:fadeOut .4s 15.7s both">{title('PASO 1', 'Busque lo que', 'necesita', 10.4, 130)}</div>
 <div class="search"><div class="mag"></div><div class="typed">óptica</div><div class="caret"></div><div class="btn">Buscar</div></div>
 <div class="card econ"><img src="f_card.png"></div>
 <div style="position:absolute;inset:0;opacity:0;animation:fadeIn .4s 16.1s both">{title('PASO 2', 'Elija y', 'escríbale directo', 16.1, 130)}
  <div class="chips"><div class="chip" style="animation-delay:17.4s"><i></i>Qué vende</div><div class="chip" style="animation-delay:17.7s"><i></i>Dónde queda</div><div class="chip" style="animation-delay:18.0s"><i></i>Su WhatsApp</div></div></div>
 {coin('pin', 300, 1580, 18.6, 240, -500, 180)}{coin('whatsapp', 780, 1580, 19.0, -240, -500, 180)}
</div>
<style>@keyframes fadeOut{{to{{opacity:0}}}}@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}</style>

<!-- S5 -->
<div class="sc s5"><div class="bg"></div><div class="glow" style="top:1000px"></div>
 {title('Y ADEMÁS', 'Todo lo útil', 'de la ciudad', 21.5, 130)}
 <div class="mapc"><img src="f_mapa.jpg"></div>
 <div class="card pop farm"><img src="f_farm.png"></div>
 <div class="card pop camb"><img src="f_cambio.png"></div>
 {coin('farm', 150, 700, 23.4, 300, 300, 170)}{coin('cajero', 930, 680, 23.8, -300, 300, 170)}{coin('cambio', 180, 1560, 24.2, 300, -300, 170)}
 <div class="sub" style="top:1720px;animation-delay:24.6s">Farmacias de turno, cajeros, cambio y más.</div>
</div>

<!-- S6 -->
<div class="sc s6"><div class="bg"></div><div class="glow" style="top:960px"></div>
 <img class="logo6" src="logo.png">
 <div class="url6">uruku.bo</div>
 <div class="nodl"><span>Sin descargar nada</span></div>
 <div class="lema">Si está en Bolivia, está en Uruku.</div>
 {coin('pin', 170, 470, 27.6, 370, 400, 150)}{coin('comida', 910, 440, 27.8, -370, 400, 150)}{coin('whatsapp', 180, 1580, 28.0, 360, -500, 150)}{coin('farm', 900, 1600, 28.2, -360, -500, 150)}
</div>
</div></body></html>'''
open('explicativo.html', 'w').write(html)
print('ok', M)
