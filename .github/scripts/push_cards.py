"""Notification image cards (1024x512, Android big-picture) for scheduled app pushes.
usage: python3 push_cards.py '<spec json>' <outdir>
spec: {"app": "القرآن الكريم الشامل", "theme": "#0f5132", "cards": [{"id": "x1", "kind": "ayah|hadith|adhkar_m|adhkar_e|wird|friday|season",
        "label": "آية اليوم", "text": "...", "ref": "البقرة: ١٥٢"}]}
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

spec = json.loads(sys.argv[1])
out = os.path.abspath(sys.argv[2])
os.makedirs(out, exist_ok=True)
FONTS = os.environ.get('AIB_FONTS', os.path.join(os.getcwd(), 'fonts'))


def ff(name, file):
    p = os.path.join(FONTS, file)
    return "@font-face{font-family:%s;src:url('file://%s')}" % (name, p) if os.path.exists(p) else ''


THEMES = {  # background gradient, accent, pattern opacity
    'ayah': ('#0b3d26', '#15734a', '#e9c46a'), 'hadith': ('#3b2a12', '#7a5523', '#f1d38a'),
    'adhkar_m': ('#0b4a6f', '#2e86ab', '#ffe08a'), 'adhkar_e': ('#1d1b4f', '#43307a', '#f4d27a'),
    'wird': ('#0d4b3c', '#1f7a63', '#f0d58c'), 'friday': ('#0b3d26', '#1e6b45', '#f2cf6b'), 'season': ('#4a1d3f', '#8a3466', '#ffd27a'),
}
CSS = ff('Quran', 'AmiriQuran-Regular.ttf') + ff('Amiri', 'Amiri-Bold.ttf') + ff('AmiriR', 'Amiri-Regular.ttf') + """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1024px;height:512px;overflow:hidden}
.c{position:relative;width:1024px;height:512px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:58px 92px 70px;color:#fff;text-align:center;direction:rtl}
.pat{position:absolute;inset:0;opacity:.13}
.frame{position:absolute;inset:18px;border:2px solid var(--a);border-radius:26px;opacity:.75}
.frame:after{content:"";position:absolute;inset:8px;border:1px solid var(--a);border-radius:20px;opacity:.5}
.glow{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,rgba(255,255,255,.14),transparent 60%)}
.lbl{position:absolute;top:30px;left:50%;transform:translateX(-50%);background:var(--a);color:#1b1407;font-family:Amiri;font-size:25px;padding:2px 26px 6px;border-radius:0 0 18px 18px;white-space:nowrap}
.t{position:relative;font-family:AmiriR,Amiri;font-size:44px;line-height:1.75;text-shadow:0 2px 10px rgba(0,0,0,.25)}
.t.q{font-family:Quran,AmiriR;line-height:1.9}
.ref{position:relative;margin-top:14px;font-family:Amiri;font-size:24px;color:var(--a)}
.app{position:absolute;bottom:26px;left:0;right:0;font-family:Amiri;font-size:21px;opacity:.85;letter-spacing:.5px}
.orn{position:absolute;width:70px;height:70px;opacity:.55}
"""
PATTERN = ('<svg class="pat" viewBox="0 0 1024 512" width="1024" height="512"><defs><pattern id="p" width="64" height="64" patternUnits="userSpaceOnUse">'
           '<path d="M32 0 L40 24 L64 32 L40 40 L32 64 L24 40 L0 32 L24 24Z" fill="none" stroke="#fff" stroke-width="1.2"/>'
           '<circle cx="32" cy="32" r="6" fill="none" stroke="#fff" stroke-width="1"/></pattern></defs><rect width="1024" height="512" fill="url(#p)"/></svg>')
ORN = '<svg class="orn" style="%s" viewBox="0 0 70 70"><path d="M35 4 L42 28 L66 35 L42 42 L35 66 L28 42 L4 35 L28 28Z" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="35" cy="35" r="8" fill="currentColor"/></svg>'


def esc(s):
    return str(s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def html(card):
    a, b, acc = THEMES.get(card.get('kind'), THEMES['ayah'])
    q = card.get('kind') == 'ayah'
    orn = ''.join(ORN % ('%s;color:%s' % (p, acc)) for p in ('top:40px;right:40px', 'top:40px;left:40px', 'bottom:40px;right:40px', 'bottom:40px;left:40px'))
    return ('<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head><body>'
            '<div class="c" style="background:linear-gradient(135deg,%s,%s);--a:%s">%s<div class="glow"></div><div class="frame"></div>%s'
            '<div class="lbl">%s</div><div class="t%s" id="t" style="font-size:%dpx">%s</div>%s<div class="app">%s</div></div>'
            '<script>const t=document.getElementById("t");let s=parseFloat(getComputedStyle(t).fontSize);'
            'const box=document.querySelector(".c");while(s>20&&(t.scrollHeight>330||t.scrollWidth>840)){s-=1.5;t.style.fontSize=s+"px";}</script>'
            '</body></html>') % (CSS, a, b, acc, PATTERN, orn, esc(card.get('label')), ' q' if q else '', (60 if len(card.get('text', '')) < 60 else 52 if len(card.get('text', '')) < 120 else 44), esc(card.get('text')),
                                 ('<div class="ref">%s</div>' % esc(card['ref'])) if card.get('ref') else '', esc(spec.get('app', '')))


done = []
with sync_playwright() as p:
    br = None
    for opt in ({'channel': 'chrome'}, {}):
        try:
            br = p.chromium.launch(**opt)
            break
        except Exception:  # noqa: BLE001
            continue
    page = br.new_page(viewport={'width': 1024, 'height': 512})
    for c in spec.get('cards', []):
        cid = ''.join(ch for ch in str(c.get('id', '')) if ch.isalnum() or ch in '-_')[:40]
        if not cid:
            continue
        hp = os.path.join(out, '_c.html')
        open(hp, 'w', encoding='utf-8').write(html(c))
        page.goto('file://' + hp)
        page.evaluate('document.fonts.ready')
        page.wait_for_timeout(120)
        page.screenshot(path=os.path.join(out, cid + '.jpg'), type='jpeg', quality=86)
        done.append(cid)
    br.close()
os.remove(os.path.join(out, '_c.html')) if os.path.exists(os.path.join(out, '_c.html')) else None
print(json.dumps({'cards': len(done)}))
