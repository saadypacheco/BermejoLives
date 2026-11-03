import sys, os, json
from playwright.sync_api import sync_playwright
html, out, fmt, cfg, fps, dur = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
times = [float(x) for x in sys.argv[7].split(',')] if len(sys.argv) > 7 else [i/fps for i in range(int(round(dur*fps)))]
cfg['fmt'] = fmt
W = 1920 if fmt == 'h' else 1080
os.makedirs(out, exist_ok=True)
js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'adapt.js')).read()
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': 1080})
    pg.goto('file://' + os.path.abspath(html)); pg.wait_for_load_state('load'); pg.wait_for_timeout(400)
    pg.evaluate(js, cfg)
    pg.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>0)))")
    pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
    pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={times[0]*1000})"); pg.screenshot(); pg.wait_for_timeout(300); pg.screenshot()
    for i, t in enumerate(times):
        pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={t*1000}); window.__upd&&__upd()")
        pg.screenshot(path=f'{out}/f{i:04d}.png' if len(sys.argv) <= 7 else f'{out}/t{t}.png')
    b.close()
