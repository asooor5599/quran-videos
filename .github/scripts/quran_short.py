"""Render a vertical Quran Short (1080x1920): nature video background + recitation of whole ayahs
+ synced Uthmani text with English translation.

usage: python3 quran_short.py '<spec json>' <outdir>
spec: {
  "folder": "Saood_ash-Shuraym_128kbps",      # everyayah.com reciter folder
  "reciterAr": "سعود الشريم", "reciterEn": "Saud Al-Shuraim",
  "surah": 67, "from": 1, "to": 5,             # 'to' = last allowed ayah (the clip may stop earlier)
  "surahName": "الملك", "surahEn": "Al-Mulk",
  "target": 20, "maxDur": 58,                  # seconds of recitation
  "bgUrl": "https://cdn.pixabay.com/....mp4"
}
env AIB_LOCAL_TEST=1 : use local files (test/ayah_SSSAAA.mp3, test/bg.mp4, test/text.json) instead of downloading.
Outputs: short.mp4, cover.jpg, info.json
"""
import json
import os
import subprocess
import sys
import urllib.request

spec = json.loads(sys.argv[1])
out = os.path.abspath(sys.argv[2])
os.makedirs(out, exist_ok=True)
work = os.path.join(out, 'work')
os.makedirs(work, exist_ok=True)
LOCAL = os.environ.get('AIB_LOCAL_TEST') == '1'
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('AIB_FONTS', os.path.join(os.getcwd(), 'fonts'))
S = int(spec['surah'])
A0, A1 = int(spec['from']), int(spec.get('to') or spec['from'])
TARGET, MAXDUR = float(spec.get('target', 20)), float(spec.get('maxDur', 58))
LEAD, TAIL = 0.7, 1.0


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def get(url, dest, tries=4):
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AIB quran shorts)'})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, 'wb') as f:
                f.write(r.read())
            if os.path.getsize(dest) > 0:
                return dest
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError('download failed: %s (%s)' % (url, last))


def dur(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).stdout.strip())


# ---------------- 1) recitation: whole ayahs until ~target seconds
ayahs, t = [], 0.0
for a in range(A0, A1 + 1):
    f = os.path.join(work, 'a%03d%03d.mp3' % (S, a))
    if LOCAL:
        src = os.path.join(HERE, 'test', 'ayah_%03d%03d.mp3' % (S, a))
        if not os.path.exists(src):
            break
        f = src
    else:
        try:
            get('https://everyayah.com/data/%s/%03d%03d.mp3' % (spec['folder'], S, a), f)
        except RuntimeError:
            if ayahs:
                break
            raise
    d = dur(f)
    if ayahs and t + d > MAXDUR:
        break
    ayahs.append({'n': a, 'file': f, 'dur': d})
    t += d
    if t >= TARGET:
        break
if not ayahs:
    raise SystemExit('no ayah audio')
if t > MAXDUR + 30:
    raise SystemExit('ayah too long for a short (%.1fs)' % t)

# ---------------- 2) text: Uthmani + Saheeh International
BASM = 'بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ'
if LOCAL:
    texts = json.load(open(os.path.join(HERE, 'test', 'text.json'), encoding='utf-8'))
else:
    texts = {}
    for a in ayahs:
        u = 'https://api.alquran.cloud/v1/ayah/%d:%d/editions/quran-uthmani,en.sahih' % (S, a['n'])
        p = os.path.join(work, 't%d.json' % a['n'])
        get(u, p)
        dd = json.load(open(p, encoding='utf-8'))['data']
        texts[str(a['n'])] = {'ar': dd[0]['text'], 'en': dd[1]['text']}
for a in ayahs:
    tx = texts[str(a['n'])]
    ar = tx['ar'].strip()
    if a['n'] == 1 and S not in (1, 9) and ar.startswith(BASM[:5]):
        w = ar.split(' ')
        ar = ' '.join(w[4:]).strip() or ar
    en = tx['en'].strip()
    while en.endswith(' -') or en.endswith('-') or en.endswith(' –'):
        en = en.rstrip(' -–').strip()
    a['ar'], a['en'] = ar, en

# ---------------- 3) audio track (lead + ayahs + tail)
lst = os.path.join(work, 'list.txt')
with open(lst, 'w') as fh:
    for a in ayahs:
        fh.write("file '%s'\n" % a['file'].replace("'", "'\\''"))
run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-ac', '2', '-ar', '44100', os.path.join(work, 'rec.wav')])
rec = dur(os.path.join(work, 'rec.wav'))
scale = rec / sum(a['dur'] for a in ayahs)  # keep text timing exact even if encoder padding differs
total = LEAD + rec + TAIL
pos = LEAD
for a in ayahs:
    a['start'] = round(pos, 3)
    pos += a['dur'] * scale
    a['end'] = round(pos, 3)

# ---------------- 4) overlays rendered by Chrome (transparent PNGs)
def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def font_face():
    def ff(name, file):
        p = os.path.join(FONTS, file)
        return "@font-face{font-family:%s;src:url('file://%s')}" % (name, p) if os.path.exists(p) else ''
    return ff('Quran', 'AmiriQuran-Regular.ttf') + ff('Amiri', 'Amiri-Bold.ttf') + ff('Ruqaa', 'ArefRuqaa-Bold.ttf') + ff('Lora', 'Lora-VF.ttf')


BASE_CSS = font_face() + """
*{margin:0;padding:0;box-sizing:border-box}html,body{width:1080px;height:1920px;background:transparent;overflow:hidden}
body{position:relative;font-family:Amiri,serif;color:#fff}
.sh{text-shadow:0 3px 14px rgba(0,0,0,.75),0 1px 3px rgba(0,0,0,.9)}
"""
header_html = """<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>%s
.top{position:absolute;top:150px;left:0;right:0;text-align:center}
.sura{font-family:Ruqaa,Amiri;font-size:96px;color:#f3dca0;line-height:1.2}
.ref{font-size:40px;color:#fff;opacity:.92;margin-top:6px}
.line{width:420px;height:2px;margin:26px auto 0;background:linear-gradient(90deg,transparent,#f3dca0,transparent)}
.bot{position:absolute;bottom:250px;left:0;right:0;text-align:center}
.rec{font-size:46px;color:#fff}
.recen{font-family:Lora,serif;font-size:30px;color:#f3dca0;opacity:.9;margin-top:4px;letter-spacing:1px}
</style></head><body>
<div class="top sh"><div class="sura">سورة %s</div><div class="ref">%s</div><div class="line"></div></div>
<div class="bot sh"><div class="rec">بصوت الشيخ %s</div><div class="recen" dir="ltr">%s</div></div>
</body></html>""" % (BASE_CSS, esc(spec['surahName']),
                     ('الآية %d' % ayahs[0]['n']) if len(ayahs) == 1 else ('الآيات %d – %d' % (ayahs[0]['n'], ayahs[-1]['n'])),
                     esc(spec['reciterAr']), esc(spec.get('reciterEn', '')))

ayah_tpl = """<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>%s
.box{position:absolute;left:70px;right:70px;top:520px;height:880px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
.ar{font-family:Quran,Amiri,serif;font-size:%dpx;line-height:1.95;color:#fff}
.num{font-family:Amiri;color:#f3dca0}
.en{font-family:Lora,serif;font-size:%dpx;line-height:1.45;color:#f6edd6;margin-top:34px;max-width:900px;font-style:italic}
</style></head><body><div class="box sh" id="b"><div class="ar" id="ar">%s <span class="num">﴿%s﴾</span></div><div class="en" id="en" dir="ltr">%s</div></div>
</body></html>"""


def ar_digits(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    run([sys.executable, '-m', 'pip', 'install', '--quiet', 'playwright'])
    from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = None
    for opt in ({'channel': 'chrome'}, {}):
        try:
            browser = p.chromium.launch(**opt)
            break
        except Exception:  # noqa: BLE001
            continue
    if browser is None:
        raise SystemExit('no chromium')
    page = browser.new_page(viewport={'width': 1080, 'height': 1920})

    def shot(html, path):
        hp = os.path.join(work, 'o.html')
        open(hp, 'w', encoding='utf-8').write(html)
        page.goto('file://' + hp)
        page.evaluate('document.fonts.ready')
        page.wait_for_timeout(150)
        page.screenshot(path=path, omit_background=True)

    shot(header_html, os.path.join(work, 'header.png'))
    for a in ayahs:
        n = len(a['ar'])
        fs = 86 if n < 60 else 76 if n < 110 else 66 if n < 170 else 58 if n < 240 else 50 if n < 330 else 44
        fe = 38 if len(a['en']) < 160 else 34 if len(a['en']) < 260 else 30 if len(a['en']) < 380 else 26
        html = ayah_tpl % (BASE_CSS, fs, fe, esc(a['ar']), ar_digits(a['n']), esc(a['en']))
        hp = os.path.join(work, 'o.html')
        open(hp, 'w', encoding='utf-8').write(html)
        page.goto('file://' + hp)
        page.evaluate('document.fonts.ready')
        # shrink until the text block fits its box
        page.evaluate("""() => { const b = document.getElementById('b'), ar = document.getElementById('ar'), en = document.getElementById('en');
          let a = parseFloat(getComputedStyle(ar).fontSize), e = parseFloat(getComputedStyle(en).fontSize), i = 0;
          while (b.scrollHeight > b.clientHeight + 2 && i++ < 40) { a *= 0.94; e *= 0.95; ar.style.fontSize = a + 'px'; en.style.fontSize = e + 'px'; } }""")
        page.wait_for_timeout(100)
        a['png'] = os.path.join(work, 'ay%d.png' % a['n'])
        page.screenshot(path=a['png'], omit_background=True)
    browser.close()

# ---------------- 5) background video
bg = os.path.join(work, 'bg.mp4')
if LOCAL:
    bg = os.path.join(HERE, 'test', 'bg.mp4')
else:
    get(spec['bgUrl'], bg)

# ---------------- 6) compose
inputs = ['-stream_loop', '-1', '-i', bg, '-i', os.path.join(work, 'rec.wav'), '-loop', '1', '-t', '%.2f' % total, '-i', os.path.join(work, 'header.png')]
for a in ayahs:
    inputs += ['-loop', '1', '-t', '%.2f' % total, '-i', a['png']]
F = 0.35
fc = ['[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,'
      'eq=saturation=0.92:brightness=-0.03,drawbox=x=0:y=0:w=iw:h=ih:color=black@0.42:t=fill,vignette=PI/5[bg]',
      '[2:v]format=rgba,fade=t=in:st=0:d=0.6:alpha=1[hd]',
      '[bg][hd]overlay=0:0:format=auto[v0]']
last = 'v0'
for i, a in enumerate(ayahs):
    k = 3 + i
    st, en = a['start'], a['end']
    if i == 0:
        st = max(0.0, st - 0.5)
    if i == len(ayahs) - 1:
        en = total - 0.2
    fc.append('[%d:v]format=rgba,fade=t=in:st=%.3f:d=%.2f:alpha=1,fade=t=out:st=%.3f:d=%.2f:alpha=1[t%d]' % (k, st, F, max(st + F, en - F), F, i))
    fc.append('[%s][t%d]overlay=0:0:format=auto:enable=\'between(t,%.3f,%.3f)\'[v%d]' % (last, i, st, en, i + 1))
    last = 'v%d' % (i + 1)
fc.append('[%s]fade=t=in:st=0:d=0.5,fade=t=out:st=%.2f:d=0.6,format=yuv420p[vout]' % (last, total - 0.6))
fc.append('[1:a]adelay=%d|%d,apad,atrim=0:%.2f,afade=t=out:st=%.2f:d=0.6[aout]' % (int(LEAD * 1000), int(LEAD * 1000), total, total - 0.6))
video = os.path.join(out, 'short.mp4')
run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error'] + inputs + ['-filter_complex', ';'.join(fc), '-map', '[vout]', '-map', '[aout]',
     '-t', '%.2f' % total, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-profile:v', 'high', '-r', '30',
     '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', video])
# cover: a frame where the first ayah is fully visible
run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-ss', '%.2f' % min(total - 0.1, ayahs[0]['start'] + 1.0), '-i', video, '-frames:v', '1', '-q:v', '3', os.path.join(out, 'cover.jpg')])
info = {'surah': S, 'from': ayahs[0]['n'], 'to': ayahs[-1]['n'], 'duration': round(total, 2), 'recitation': round(rec, 2),
        'ayahs': [{'n': a['n'], 'ar': a['ar'], 'en': a['en'], 'start': a['start'], 'end': a['end']} for a in ayahs]}
json.dump(info, open(os.path.join(out, 'info.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('short ok: %d:%d-%d %.1fs %d bytes' % (S, info['from'], info['to'], total, os.path.getsize(video)))
