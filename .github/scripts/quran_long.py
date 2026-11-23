"""Render a full-surah video (1280x720) like the Shorts design: moving nature background + Uthmani ayah text
with English translation, synced to the recitation using mp3quran ayah timings, then upload it straight to a
YouTube resumable-upload session created by n8n (so the big file never passes through n8n).

usage: python3 quran_long.py '<spec json>' <outdir>
spec: {"surah":12,"surahName":"يوسف","surahEn":"Yusuf","reciterAr":"سعود الشريم","reciterEn":"Saud Al-Shuraim",
       "read":31, "audioUrl":"https://.../012.mp3", "bgUrls":["https://cdn.pixabay.com/...mp4", ...]}
env  UPLOAD_URL  YouTube resumable session URL (optional; without it the video is only rendered)
     AIB_LOCAL_TEST=1  use test/ files (long_audio.mp3, timing.json, surah.json, bg.mp4)
Outputs: video.mp4 (unless uploaded and AIB_KEEP=0), info.json {videoId, duration, ayahs}
"""
import json
import os
import random
import subprocess
import sys
import time
import urllib.request

spec = json.loads(sys.argv[1])
out = os.path.abspath(sys.argv[2])
work = os.path.join(out, 'work')
os.makedirs(work, exist_ok=True)
LOCAL = os.environ.get('AIB_LOCAL_TEST') == '1'
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('AIB_FONTS', os.path.join(os.getcwd(), 'fonts'))
S = int(spec['surah'])
W, H, FPS = 1280, 720, 24
T0 = time.time()


def log(*a):
    print('[%5.0fs]' % (time.time() - T0), *a, flush=True)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def get(url, dest, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (AIB quran)'})
            with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            if os.path.getsize(dest) > 0:
                return dest
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError('download failed: %s (%s)' % (url, last))


def getjson(url):
    p = os.path.join(work, 'j%d.json' % (abs(hash(url)) % 10 ** 8))
    get(url, p)
    return json.load(open(p, encoding='utf-8'))


def dur(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).stdout.strip())


# ---------------- 1) audio, timings, text
if LOCAL:
    audio = os.path.join(HERE, 'test', 'long_audio.mp3')
    timing = json.load(open(os.path.join(HERE, 'test', 'timing.json')))
    surah = json.load(open(os.path.join(HERE, 'test', 'surah.json'), encoding='utf-8'))
else:
    audio = get(spec['audioUrl'], os.path.join(work, 'audio.mp3'))
    timing = getjson('https://www.mp3quran.net/api/v3/ayat_timing?surah=%d&read=%d' % (S, int(spec['read']))) if int(spec.get('read') or 0) else []
    surah = getjson('https://api.alquran.cloud/v1/surah/%d/editions/quran-uthmani,en.sahih' % S)
total = dur(audio)
log('audio', round(total), 's')
ar_list = surah['data'][0]['ayahs']
en_list = surah['data'][1]['ayahs']
BASM = 'بِسْمِ'
segs = []  # (start, end, ayah) ; ayah 0 = intro
for t in timing:
    a = int(t['ayah'])
    st, en = float(t['start_time']) / 1000, float(t['end_time']) / 1000
    if en <= st or a < 0 or a > len(ar_list):
        continue
    segs.append([st, min(en, total), a])
segs.sort()
if not segs:  # no ayah timings for this reciter: same design, title + basmala at the start, then the nature video
    segs = [[0.0, min(8.0, total), 0], [min(8.0, total), total, -1]]
    log('no ayah timings — title-only mode')
# make segments contiguous (text stays until the next ayah starts)
for i in range(len(segs) - 1):
    segs[i][1] = segs[i + 1][0]
segs[-1][1] = total
texts = {}
for i, (ar, en) in enumerate(zip(ar_list, en_list), 1):
    a_txt = ar['text'].strip()
    if i == 1 and S not in (1, 9) and a_txt.startswith(BASM):
        a_txt = ' '.join(a_txt.split(' ')[4:]).strip() or a_txt
    e_txt = en['text'].strip()
    while e_txt.endswith('-') or e_txt.endswith('–'):
        e_txt = e_txt.rstrip(' -–').strip()
    texts[i] = (a_txt, e_txt)
log('ayahs', len(texts), 'segments', len(segs))

# ---------------- 2) overlays (Chrome, transparent PNG)
def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def ff(name, file):
    p = os.path.join(FONTS, file)
    return "@font-face{font-family:%s;src:url('file://%s')}" % (name, p) if os.path.exists(p) else ''


CSS = ff('Quran', 'AmiriQuran-Regular.ttf') + ff('Amiri', 'Amiri-Bold.ttf') + ff('Ruqaa', 'ArefRuqaa-Bold.ttf') + ff('Lora', 'Lora-VF.ttf') + """
*{margin:0;padding:0;box-sizing:border-box}html,body{width:%dpx;height:%dpx;background:transparent;overflow:hidden}
body{position:relative;font-family:Amiri,serif;color:#fff}.sh{text-shadow:0 2px 10px rgba(0,0,0,.8),0 1px 2px rgba(0,0,0,.9)}
""" % (W, H)
AR = lambda n: str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))
header = """<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>%s
.top{position:absolute;top:26px;left:0;right:0;text-align:center}
.s{font-family:Ruqaa,Amiri;font-size:46px;color:#f3dca0;line-height:1.2}
.l{width:260px;height:1.5px;margin:6px auto 0;background:linear-gradient(90deg,transparent,#f3dca0,transparent)}
.bot{position:absolute;bottom:22px;left:0;right:0;text-align:center;font-size:24px}
.bot span{font-family:Lora,serif;font-size:17px;color:#f3dca0;margin-right:10px}
</style></head><body><div class="top sh"><div class="s">سورة %s</div><div class="l"></div></div>
<div class="bot sh">بصوت الشيخ %s <span dir="ltr">%s</span></div></body></html>""" % (CSS, esc(spec['surahName']), esc(spec['reciterAr']), esc(spec.get('reciterEn', '')))
intro = """<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>%s
.c{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.b{font-family:Quran,Amiri;font-size:58px;color:#fff}.e{font-family:Lora,serif;font-size:24px;color:#f6edd6;margin-top:18px;font-style:italic}
</style></head><body><div class="c sh"><div class="b">%s</div><div class="e" dir="ltr">%s</div></div></body></html>"""
ayah_tpl = """<!doctype html><html dir="rtl"><head><meta charset="utf-8"><style>%s
.box{position:absolute;left:90px;right:90px;top:120px;bottom:90px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}
.ar{font-family:Quran,Amiri,serif;font-size:%dpx;line-height:1.9;color:#fff}.num{font-family:Amiri;color:#f3dca0}
.en{font-family:Lora,serif;font-size:%dpx;line-height:1.4;color:#f6edd6;margin-top:18px;max-width:1000px;font-style:italic}
</style></head><body><div class="box sh" id="b"><div class="ar" id="ar">%s <span class="num">﴿%s﴾</span></div><div class="en" id="en" dir="ltr">%s</div></div></body></html>"""
FIT = """() => { const b = document.getElementById('b'), ar = document.getElementById('ar'), en = document.getElementById('en');
  let a = parseFloat(getComputedStyle(ar).fontSize), e = parseFloat(getComputedStyle(en).fontSize), i = 0;
  while (b.scrollHeight > b.clientHeight + 2 && i++ < 60) { a *= 0.94; e = Math.max(11, e * 0.95); ar.style.fontSize = a + 'px'; en.style.fontSize = e + 'px'; } }"""
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    run([sys.executable, '-m', 'pip', 'install', '--quiet', 'playwright'])
    from playwright.sync_api import sync_playwright
pngs = {}
with sync_playwright() as p:
    br = None
    for opt in ({'channel': 'chrome'}, {}):
        try:
            br = p.chromium.launch(**opt)
            break
        except Exception:  # noqa: BLE001
            continue
    page = br.new_page(viewport={'width': W, 'height': H})

    def shot(html, path, fit=False):
        hp = os.path.join(work, 'o.html')
        open(hp, 'w', encoding='utf-8').write(html)
        page.goto('file://' + hp)
        page.evaluate('document.fonts.ready')
        if fit:
            page.evaluate(FIT)
        page.screenshot(path=path, omit_background=True)

    shot(header, os.path.join(work, 'header.png'))
    if S == 9:
        shot(intro % (CSS, 'أَعُوذُ بِاللَّهِ مِنَ الشَّيْطَانِ الرَّجِيمِ', 'I seek refuge in Allah from Satan, the expelled'), os.path.join(work, 'ay0.png'))
    else:
        shot(intro % (CSS, 'بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ', 'In the name of Allah, the Entirely Merciful, the Especially Merciful'), os.path.join(work, 'ay0.png'))
    pngs[0] = os.path.join(work, 'ay0.png')
    shot('<!doctype html><html><head><style>%s</style></head><body></body></html>' % CSS, os.path.join(work, 'blank.png'))
    for a, (ar, en) in texts.items():
        n = len(ar)
        fs = 52 if n < 80 else 46 if n < 160 else 40 if n < 260 else 34 if n < 400 else 28 if n < 650 else 22
        fe = 24 if len(en) < 200 else 21 if len(en) < 380 else 18 if len(en) < 650 else 15
        pth = os.path.join(work, 'ay%d.png' % a)
        shot(ayah_tpl % (CSS, fs, fe, esc(ar), AR(a), esc(en)), pth, fit=True)
        pngs[a] = pth
    br.close()
log('overlays done')

# text track: one short clip per ayah with a soft fade in/out (like the Shorts), joined into one transparent track
from concurrent.futures import ThreadPoolExecutor
TF, FADE = 12, 0.35
items, t = [], 0.0
for st, en, a in segs:
    if st > t + 0.05:
        items.append((os.path.join(work, 'blank.png'), st - t, False))
    items.append((pngs.get(a, os.path.join(work, 'blank.png')), en - st, a in pngs))
    t = en


def mk(i_item):
    i, (png, d, fade) = i_item
    d = max(d, 1.0 / TF)
    dst = os.path.join(work, 'tx%04d.mov' % i)
    vf = 'fps=%d,format=rgba' % TF
    if fade and d > 2 * FADE + 0.2:
        vf += ',fade=t=in:st=0:d=%.2f:alpha=1,fade=t=out:st=%.3f:d=%.2f:alpha=1' % (FADE, d - FADE, FADE)
    run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', str(TF), '-t', '%.3f' % d, '-i', png,
         '-vf', vf, '-t', '%.3f' % d, '-c:v', 'qtrle', '-pix_fmt', 'argb', dst])
    return dst


with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
    parts = list(ex.map(mk, enumerate(items)))
tl = os.path.join(work, 'text.txt')
with open(tl, 'w') as fh:
    for f in parts:
        fh.write("file '%s'\n" % f)
log('text track', len(parts), 'clips')

# ---------------- 3) background: several nature clips, normalised and looped in shuffled order
clips = []
urls = [os.path.join(HERE, 'test', 'bg.mp4')] if LOCAL else list(spec.get('bgUrls') or [])
for i, u in enumerate(urls[:14]):
    try:
        src = u if LOCAL else get(u, os.path.join(work, 'raw%d.mp4' % i), tries=2)
        dst = os.path.join(work, 'bg%d.mp4' % i)
        run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-i', src, '-an', '-t', '40',
             '-vf', 'scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,fps=%d,eq=saturation=0.9:brightness=-0.03,'
                    'drawbox=x=0:y=0:w=iw:h=ih:color=black@0.42:t=fill,vignette=PI/5,format=yuv420p' % (W, H, W, H, FPS),
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-g', str(FPS * 2), dst])
        if dur(dst) >= 4:
            clips.append((dst, dur(dst)))
    except Exception as e:  # noqa: BLE001
        log('bg skip', i, e)
if not clips:
    raise SystemExit('no background clips')
bl = os.path.join(work, 'bg.txt')
with open(bl, 'w') as fh:
    t, order = 0.0, []
    while t < total + 5:
        if not order:
            order = clips[:]
            random.shuffle(order)
        c = order.pop()
        fh.write("file '%s'\n" % c[0])
        t += c[1]
log('bg clips', len(clips))

# ---------------- 4) compose
video = os.path.join(out, 'video.mp4')
fc = ('[0:v]setpts=PTS-STARTPTS[bg];[2:v]format=rgba[hd];[1:v]fps=%d,format=rgba[tx];'
      '[bg][hd]overlay=0:0[v1];[v1][tx]overlay=0:0:eof_action=pass,format=yuv420p[v]') % FPS
run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', bl,
     '-f', 'concat', '-safe', '0', '-i', tl, '-loop', '1', '-i', os.path.join(work, 'header.png'), '-i', audio,
     '-filter_complex', fc, '-map', '[v]', '-map', '3:a', '-t', '%.2f' % total,
     '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '27', '-maxrate', '1800k', '-bufsize', '3600k', '-r', str(FPS), '-g', str(FPS * 4),
     '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', video])
size = os.path.getsize(video)
log('video', round(size / 1e6, 1), 'MB')

# ---------------- 5) upload to the YouTube resumable session
info = {'surah': S, 'duration': round(total, 1), 'size': size, 'ayahs': len(texts), 'videoId': None}
up = os.environ.get('UPLOAD_URL', '')
if up:
    import http.client
    from urllib.parse import urlparse
    u = urlparse(up)
    offset, vid, CH = 0, None, 64 << 20
    with open(video, 'rb') as f:
        for attempt in range(40):
            try:
                if offset >= size:
                    break
                f.seek(offset)
                chunk = f.read(CH)
                end = offset + len(chunk) - 1
                conn = http.client.HTTPSConnection(u.netloc, timeout=600)
                conn.request('PUT', u.path + ('?' + u.query if u.query else ''), body=chunk,
                             headers={'Content-Type': 'video/mp4', 'Content-Length': str(len(chunk)), 'Content-Range': 'bytes %d-%d/%d' % (offset, end, size)})
                r = conn.getresponse()
                body = r.read()
                if r.status in (200, 201):
                    vid = json.loads(body).get('id')
                    offset = size
                    break
                if r.status == 308:
                    rg = r.getheader('Range')
                    offset = int(rg.split('-')[1]) + 1 if rg else 0
                    log('uploaded', round(offset / size * 100), '%')
                    continue
                raise RuntimeError('upload HTTP %d %s' % (r.status, body[:200]))
            except Exception as e:  # noqa: BLE001
                log('upload retry', attempt, e)
                time.sleep(min(60, 5 * (attempt + 1)))
                try:  # ask the session how much it already has
                    conn = http.client.HTTPSConnection(u.netloc, timeout=120)
                    conn.request('PUT', u.path + ('?' + u.query if u.query else ''), headers={'Content-Length': '0', 'Content-Range': 'bytes */%d' % size})
                    r = conn.getresponse()
                    r.read()
                    if r.status == 308:
                        rg = r.getheader('Range')
                        offset = int(rg.split('-')[1]) + 1 if rg else 0
                except Exception:  # noqa: BLE001
                    pass
    if not vid:
        raise SystemExit('YouTube upload failed')
    info['videoId'] = vid
    log('youtube id', vid)
json.dump(info, open(os.path.join(out, 'info.json'), 'w'))
print('long ok', json.dumps(info))
