from PIL import Image
Image.open('p_motero.jpg').crop((0, 0, 605, 1228)).save('p_motero_c.jpg', quality=93)

def scene(name, t0, t1, fin=0.4, fout=0.4):
    dur = t1 - t0; p1 = fin/dur*100; p2 = 100 - fout/dur*100
    return (f"@keyframes io_{name}{{0%{{opacity:0}}{p1:.2f}%{{opacity:1}}{p2:.2f}%{{opacity:1}}100%{{opacity:0}}}}\n"
            f".{name}{{animation:io_{name} {dur}s {t0}s linear both}}\n")

WA = ('<svg viewBox="0 0 24 24" width="64" height="64"><path fill="#fff" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .1-3.2-.8-2.7-1.1-4.4-3.9-4.5-4.1-.1-.2-1.1-1.4-1.1-2.7s.7-1.9.9-2.2c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.4.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.9-1c.2-.3.4-.2.7-.1l1.9.9c.3.1.5.2.5.3.1.2.1.6-.2 1.2z"/></svg>')

BASE = '''*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;background:#08110C}
.stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:radial-gradient(110% 75% at 50% 55%,#0F3423 0%,#0B1E15 45%,#08110C 100%)}
.sc{position:absolute;inset:0}
.glow{position:absolute;left:540px;top:1000px;width:1250px;height:1250px;margin:-625px 0 0 -625px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(38,185,105,.55),rgba(29,141,82,.22) 50%,transparent 74%);filter:blur(24px);animation:pulse 4s ease-in-out infinite}
@keyframes pulse{50%{transform:scale(1.07)}}
.title{position:absolute;left:0;right:0;text-align:center;padding:0 60px}
.kick{display:inline-block;font-weight:600;font-size:30px;letter-spacing:3px;color:#04311A;background:#34D27F;border-radius:30px;padding:8px 24px;margin-bottom:22px;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.tl1,.tl2{font-weight:600;font-size:88px;line-height:1.05;letter-spacing:-2.5px;color:#fff;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.tl2{color:#34D27F}
@keyframes rise{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
.sub{position:absolute;left:0;right:0;text-align:center;font-size:38px;line-height:1.35;color:#D2E2D8;padding:0 90px;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.pc{position:absolute;border-radius:44px;overflow:hidden;background:#f2f2f0;
 box-shadow:0 50px 100px rgba(0,0,0,.6),0 0 0 3px rgba(80,220,140,.45),0 0 80px rgba(52,210,127,.35)}
.pc img{display:block;width:100%;height:100%;object-fit:cover}
.chip{position:absolute;font-weight:600;font-size:40px;color:#fff;background:#16211B;border:2px solid #2B4A39;border-radius:44px;padding:16px 34px;display:flex;align-items:center;gap:16px;
 box-shadow:0 24px 48px rgba(0,0,0,.5);white-space:nowrap}
.chip i{width:18px;height:18px;border-radius:50%;background:#34D27F;box-shadow:0 0 16px #34D27F;flex:none}
.coin{position:absolute;filter:drop-shadow(0 24px 30px rgba(0,0,0,.6));animation:cpop .9s cubic-bezier(.2,1.35,.3,1) both, bob 3s ease-in-out infinite}
@keyframes cpop{from{opacity:0;transform:scale(.15) rotate(-40deg)}}
@keyframes bob{50%{translate:0 -12px}}
@keyframes pop{from{opacity:0;transform:scale(.4) rotate(-6deg)}}
.logoE{position:absolute;width:420px;left:330px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}
.url{position:absolute;left:0;right:0;text-align:center;font-weight:700;font-size:80px;color:#34D27F;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}
.lema{position:absolute;left:0;right:0;text-align:center;font-size:34px;color:#A8BDB1;animation:rise .7s both}
'''

def title(k, l1, l2, t, top):
    kk = f'<div class="kick" style="animation-delay:{t}s">{k}</div>' if k else ''
    return (f'<div class="title" style="top:{top}px">{kk}<div class="tl1" style="animation-delay:{t+.1}s">{l1}</div>'
            f'<div class="tl2" style="animation-delay:{t+.25}s">{l2}</div></div>')

def coin(n, x, y, t, s=170):
    return f'<img class="coin" src="ic_{n}.png" style="left:{x-s/2}px;top:{y-s/2}px;width:{s}px;animation-delay:{t}s,{t+.9}s">'

# ---------------- Reel A: minorista ----------------
TA = 13.5
prods = [('p_modelo.jpg', 'Eco cuero con cinturón', '50% 20%'),
         ('p_motero_c.jpg', 'Estilo motero', '50% 30%'),
         ('p_corta.jpg', 'Corta, con botones dorados', '50% 50%'),
         ('p_dobleface.jpg', 'Doble faz, con capucha', '50% 50%')]
css = BASE + scene('a1', 0, 10.0, .3, .4) + scene('a2', 9.7, TA + .5, .4, .01)
css += '''
.car{position:absolute;left:150px;top:560px;width:780px;height:980px}
.slide{position:absolute;inset:0;animation:sin .7s cubic-bezier(.2,.9,.3,1) both, sout .55s cubic-bezier(.6,0,.8,.4) both}
@keyframes sin{from{opacity:0;transform:translateX(700px) rotate(10deg) scale(.85)}}
@keyframes sout{to{opacity:0;transform:translateX(-760px) rotate(-10deg) scale(.85)}}
.slide .pc{left:0;top:0;width:780px;height:980px}
.slide .chip{left:50%;bottom:-40px;transform:translateX(-50%)}
.cnt{position:absolute;left:0;right:0;top:1640px;display:flex;justify-content:center;gap:16px}
.cnt b{width:16px;height:16px;border-radius:50%;background:#2B4A39;animation:on .3s both}
@keyframes on{to{background:#34D27F;box-shadow:0 0 14px #34D27F;width:46px;border-radius:10px}}
.search{position:absolute;left:70px;right:70px;top:640px;height:130px;border-radius:32px;background:#16211B;border:2px solid #2B4A39;
 display:flex;align-items:center;padding-left:36px;gap:24px;box-shadow:0 30px 60px rgba(0,0,0,.55),0 0 50px rgba(52,210,127,.25);animation:rise .6s 10.0s both}
.mag{width:42px;height:42px;border:5px solid #8FA79A;border-radius:50%;position:relative;flex:none}
.mag:after{content:"";position:absolute;width:5px;height:18px;background:#8FA79A;right:-10px;bottom:-13px;transform:rotate(-45deg);border-radius:2px}
.typed{font-size:48px;color:#fff;font-weight:500;white-space:nowrap;overflow:hidden;width:0;animation:type .9s 10.5s steps(8) both}
@keyframes type{to{width:262px}}
.btn{margin-left:auto;height:100%;padding:0 46px;display:grid;place-items:center;font-weight:700;font-size:40px;color:#fff;background:#1F9D58;border-radius:0 30px 30px 0}
.whw{position:absolute;left:0;right:0;top:880px;display:flex;justify-content:center;animation:rise .6s 11.3s both}.whw .chip{position:relative}
'''
slides = ''
for i, (img, lab, pos) in enumerate(prods):
    t_in = 1.5 + i*2.1; t_out = t_in + 2.0 if i < 3 else 9.6
    slides += (f'<div class="slide" style="animation-delay:{t_in}s,{t_out}s"><div class="pc"><img src="{img}" style="object-position:{pos}"></div>'
               f'<div class="chip"><i></i>{lab}</div></div>')
dots = ''.join(f'<b style="animation-delay:{1.5+i*2.1}s"></b>' for i in range(4))
A = f'''<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="stage">
<div class="glow"></div>
<div class="sc a1">
 {title('NUEVA TEMPORADA', 'Camperas que', 'ya llegaron', .2, 130)}
 <div class="car">{slides}</div>
 <div class="cnt">{dots}</div>
 <div class="sub" style="top:1730px;animation-delay:1.2s">Eco cuero, doble faz y más modelos</div>
</div>
<div class="sc a2">
 {title(None, '¿Dónde las', 'consigue?', 9.8, 260)}
 <div class="search"><div class="mag"></div><div class="typed">camperas</div><div class="btn">Buscar</div></div>
 <div class="whw"><div class="chip"><i></i>Comercio de ejemplo · Bermejo</div></div>
 {coin('pin', 170, 1130, 11.6)}{coin('whatsapp', 910, 1130, 11.9)}
 <div class="sub" style="top:1060px;animation-delay:11.8s;font-size:36px">Consulte precio y talles<br>directo con el local</div>
 <img class="logoE" src="logo.png" style="top:1360px;animation-delay:12.2s">
 <div class="url" style="top:1530px;animation-delay:12.4s">uruku.bo</div>
 <div class="lema" style="top:1660px;animation-delay:12.6s">Si está en Bolivia, está en Uruku.</div>
</div>
</div></body></html>'''
open('reel_minorista.html', 'w').write(A)

# ---------------- Reel B: mayorista ----------------
TB = 14.0
css = BASE + scene('b1', 0, 3.6, .3, .4) + scene('b2', 3.3, 9.9) + scene('b3', 9.6, TB + .5, .4, .01)
css += '''
.hookbig{position:absolute;left:0;right:0;top:620px;text-align:center}
.hookbig .tl1{font-size:110px}.hookbig .tl2{font-size:110px}
.q{position:absolute;left:0;right:0;top:1120px;text-align:center;font-size:42px;color:#D2E2D8;animation:rise .6s 1.4s both;padding:0 100px;line-height:1.35}
.g{position:absolute;animation:pop .7s cubic-bezier(.2,1.3,.3,1) both, bob 3.4s ease-in-out infinite}
.g .pc{position:relative;inset:auto;width:100%;height:100%}
.code{position:absolute;left:22px;top:22px;font-weight:700;font-size:26px;color:#04311A;background:#34D27F;border-radius:14px;padding:6px 14px;z-index:2}
.chipsB{position:absolute;left:0;right:0;top:1550px;display:flex;justify-content:center;flex-wrap:wrap;gap:20px;padding:0 50px}
.chipsB .chip{position:relative;font-size:34px;padding:14px 28px;animation:rise .5s both}
.wabtn{position:absolute;left:110px;right:110px;top:760px;height:170px;border-radius:90px;background:#1F9D58;display:flex;align-items:center;justify-content:center;gap:26px;
 font-weight:700;font-size:76px;color:#fff;box-shadow:0 30px 60px rgba(0,0,0,.5),0 0 80px rgba(52,210,127,.55);animation:pop .8s 10.2s cubic-bezier(.2,1.3,.3,1) both, beat 1.4s 11.2s ease-in-out infinite}
@keyframes beat{50%{transform:scale(1.04)}}
.steps{position:absolute;left:110px;right:110px;top:1000px;display:flex;flex-direction:column;gap:20px}
.st{display:flex;align-items:center;gap:24px;font-size:36px;color:#fff;font-weight:500;background:#16211B;border:2px solid #2B4A39;border-radius:30px;padding:20px 28px;animation:rise .5s both}
.st b{width:56px;height:56px;border-radius:50%;background:#34D27F;color:#04311A;display:grid;place-items:center;font-size:30px;flex:none}
'''
grid = [('p_trench3.jpg', '166232', 60, 520, 470, 470, '50% 40%', 3.6),
        ('p_corta.jpg', 'KK61331', 550, 520, 470, 470, '50% 40%', 3.9),
        ('p_motero_c.jpg', '6052', 60, 1020, 470, 470, '50% 25%', 4.2),
        ('p_dobleface.jpg', '8806-2', 550, 1020, 470, 470, '50% 50%', 4.5)]
g = ''.join(f'<div class="g" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;animation-delay:{t}s,{t+.8}s"><div class="code">Cód. {c}</div>'
            f'<div class="pc"><img src="{im}" style="object-position:{p}"></div></div>' for im, c, x, y, w, h, p, t in grid)
B = f'''<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="stage">
<div class="glow"></div>
<div class="sc b1">
 <div class="hookbig">{title('PARA EMPRENDER', '¿Quiere', 'vender ropa?', .2, 0).replace('style="top:0px"', '')}</div>
 <div class="q">El problema no es vender.<br>Es saber dónde comprar.</div>
</div>
<div class="sc b2">
 {title('PROVEEDOR DIRECTO', 'Camperas', 'por mayor', 3.5, 130)}
 {g}
 <div class="chipsB"><div class="chip" style="animation-delay:5.6s"><i></i>Venta por docena</div><div class="chip" style="animation-delay:5.9s"><i></i>Talles S a 3XL</div><div class="chip" style="animation-delay:6.2s"><i></i>Varios colores</div></div>
 <div class="sub" style="top:1750px;animation-delay:6.8s">Precio de mayorista: consúltelo por WhatsApp</div>
</div>
<div class="sc b3">
 {title(None, 'Le pasamos', 'el contacto', 9.7, 300)}
 <div class="wabtn">{WA} 67 671 888</div>
 <div class="steps">
  <div class="st" style="animation-delay:10.9s"><b>1</b>Escríbale a Uruku</div>
  <div class="st" style="animation-delay:11.2s"><b>2</b>Diga el código del producto</div>
  <div class="st" style="animation-delay:11.5s"><b>3</b>Hable directo con el proveedor</div>
 </div>
 <img class="logoE" src="logo.png" style="top:1530px;width:360px;left:360px;animation-delay:12.2s">
 <div class="lema" style="top:1690px;animation-delay:12.5s">Si está en Bolivia, está en Uruku.</div>
</div>
</div></body></html>'''
open('reel_mayorista.html', 'w').write(B)
print('ok')
