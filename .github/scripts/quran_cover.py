"""Render the surah cover (1280x720) for any reciter with headless Chrome.

usage: python3 quran_cover.py '<json>' out.png
json: {"n":8,"name":"الأنفال","en":"Al-Anfal","meaning":"The Spoils of War","ayahs":75,"type":"D","juz":9,"reciter":"سعود الشريم"}
Fonts (Aref Ruqaa, Amiri, Cinzel) are downloaded next to the HTML by the workflow step.
"""
import html, json, os, subprocess, sys

c = json.loads(sys.argv[1])
out = sys.argv[2]
n = int(c['n'])
PAL = [('#0b3d2e', '#14573f', '#e2c27a'), ('#0d1f3c', '#1b3767', '#e6c77f'), ('#4a0f1c', '#74182c', '#f0cf8a'),
       ('#083c40', '#0f5e63', '#e8d39a'), ('#2a1446', '#46246f', '#e9c98a'), ('#141414', '#2b2b2b', '#d9b25f'),
       ('#102d52', '#1d4f86', '#f2dca6'), ('#3a2a12', '#5f4520', '#f3d590')]
d, l, g = PAL[(n - 1) % len(PAL)]
e = lambda s: html.escape(str(s))
name = str(c['name'])
big = 210 if len(name) <= 4 else 180 if len(name) <= 7 else 150
rec = str(c.get('reciter') or '')
recsize = 44 if len(rec) <= 16 else 38 if len(rec) <= 24 else 32
star = ("<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120' viewBox='0 0 120 120'><g fill='none' stroke='%s' stroke-opacity='0.10' "
        "stroke-width='1.2'><rect x='35' y='35' width='50' height='50'/><rect x='35' y='35' width='50' height='50' transform='rotate(45 60 60)'/>"
        "<circle cx='60' cy='60' r='9'/><path d='M0 60H25M95 60H120M60 0V25M60 95V120'/></g></svg>") % g
import base64
pat = 'data:image/svg+xml;base64,' + base64.b64encode(star.encode()).decode()
ay = int(c.get('ayahs') or 0)
page = f"""<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>
@font-face{{font-family:Ruqaa;src:url(fonts/ArefRuqaa-Bold.ttf)}}
@font-face{{font-family:Amiri;src:url(fonts/Amiri-Bold.ttf)}}
@font-face{{font-family:Cinzel;src:url(fonts/Cinzel-VF.ttf)}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1280px;height:720px;overflow:hidden}}
body{{background:radial-gradient(ellipse at 50% 45%,{l} 0%,{d} 70%);position:relative;font-family:Amiri}}
.pat{{position:absolute;inset:0;background-image:url("{pat}");background-size:120px}}
.fr{{position:absolute;inset:28px;border:3px solid {g}}}
.fr2{{position:absolute;inset:40px;border:1.5px solid {g};opacity:.75}}
.c{{position:absolute;width:46px;height:46px;border:2px solid {g};transform:rotate(45deg);background:{d}}}
.c::after{{content:'';position:absolute;inset:12px;border:2px solid {g};border-radius:50%}}
.ring{{position:absolute;left:50%;top:50%;width:600px;height:600px;margin:-300px 0 0 -300px;border-radius:50%;border:1.5px solid {g};opacity:.25}}
.gold{{background:linear-gradient(180deg,#fff3cf 0%,{g} 45%,#a87b2f 100%);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 4px 6px rgba(0,0,0,.45))}}
.sura{{position:absolute;top:92px;width:100%;text-align:center;font-size:58px;color:#f6ecd2;opacity:.9}}
.name{{position:absolute;top:172px;width:100%;text-align:center;font-family:Ruqaa;font-size:{big}px;line-height:1.35}}
.en{{position:absolute;top:470px;width:100%;text-align:center;font-family:Cinzel;font-weight:700;font-size:34px;letter-spacing:2px;color:{g}}}
.mean{{font-family:Cinzel;font-weight:400;font-size:24px;opacity:.85;letter-spacing:1px}}
.rec{{position:absolute;bottom:92px;width:100%;text-align:center;font-size:{recsize}px;color:#fbf6ea}}
.info{{position:absolute;bottom:58px;width:100%;text-align:center;font-size:28px;color:{g};opacity:.95}}
.badge{{position:absolute;top:66px;right:78px;width:110px;height:110px;display:flex;align-items:center;justify-content:center}}
.badge::before,.badge::after{{content:'';position:absolute;inset:14px;border:2.5px solid {g};background:{d}}}
.badge::after{{transform:rotate(45deg)}}
.badge span{{position:relative;z-index:2;font-family:Cinzel;font-weight:700;font-size:36px;color:{g}}}
.line{{position:absolute;top:455px;left:50%;width:380px;margin-left:-190px;height:1.5px;background:linear-gradient(90deg,transparent,{g},transparent)}}
</style></head><body><div class="pat"></div><div class="ring"></div><div class="fr"></div><div class="fr2"></div>
<div class="c" style="left:28px;top:28px;margin:-23px"></div><div class="c" style="right:28px;top:28px;margin:-23px"></div>
<div class="c" style="left:28px;bottom:28px;margin:-23px"></div><div class="c" style="right:28px;bottom:28px;margin:-23px"></div>
<div class="badge"><span>{n}</span></div>
<div class="sura">سورة</div><div class="name gold">{e(name)}</div><div class="line"></div>
<div class="en" dir="ltr">SURAH {e(str(c.get('en','')).upper())} <span class="mean">· {e(c.get('meaning',''))}</span></div>
<div class="rec">بصوت الشيخ {e(rec)}</div>
<div class="info">الآيات {ay} · {'مكية' if c.get('type') == 'M' else 'مدنية'} · الجزء {e(c.get('juz',''))}</div>
</body></html>"""
here = os.path.dirname(os.path.abspath(out))
hp = os.path.join(here, 'cover.html')
open(hp, 'w', encoding='utf-8').write(page)
chrome = next((p for p in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser') if subprocess.run(['which', p], capture_output=True).returncode == 0), None)
if not chrome:
    sys.exit('chrome not found')
subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=1',
                '--window-size=1280,720', '--virtual-time-budget=4000', '--screenshot=' + os.path.abspath(out), 'file://' + hp],
               check=True, capture_output=True, timeout=120)
print('cover ok', os.path.getsize(out))
