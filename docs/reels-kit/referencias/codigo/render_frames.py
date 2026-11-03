import sys,os
from playwright.sync_api import sync_playwright
html,out,fps,dur=sys.argv[1],sys.argv[2],int(sys.argv[3]),float(sys.argv[4])
times=[float(x) for x in sys.argv[5].split(',')] if len(sys.argv)>5 else [i/fps for i in range(int(dur*fps))]
os.makedirs(out,exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1080,'height':1920})
    pg.goto('file://'+os.path.abspath(html)); pg.wait_for_load_state('load'); pg.wait_for_timeout(500)
    pg.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>0)))"); pg.evaluate("document.getAnimations().forEach(a=>a.pause())")
    pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={times[0]*1000})"); pg.screenshot(); pg.wait_for_timeout(300)
    for i,t in enumerate(times):
        pg.evaluate(f"document.getAnimations().forEach(a=>a.currentTime={t*1000})")
        pg.screenshot(path=f'{out}/f{i:04d}.png' if len(sys.argv)<=5 else f'{out}/t{t}.png')
    b.close()
