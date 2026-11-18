"""Build the static textbook site from Google Docs markdown exports.
Usage: python3 build.py raw_dir figures_dir out_dir
"""
import base64, html, json, os, re, shutil, sys
import markdown

RAW, FIGS, OUT = sys.argv[1:4]
BOOK = "On Argumentation and Debate"
EDITION = "Draft edition, November 2026"

def load_chapters():
    chs = []
    for fn in sorted(os.listdir(RAW)):
        m = re.match(r'ch(\d\d)\.md$', fn)
        if m:
            chs.append((int(m.group(1)), open(os.path.join(RAW, fn), encoding='utf-8').read()))
    return chs

def strip_bold_heading(s):
    return re.sub(r'^\*\*(.*)\*\*$', r'\1', s.strip())

def slug(s):
    s = re.sub(r'<[^>]+>', '', s).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s

# ---------- figures ----------
def figure_files():
    out = {}
    for fn in os.listdir(FIGS):
        m = re.match(r'fig-(\d+)-(\d+)-.*\.(svg|png)$', fn)
        if m:
            k = f"{int(m.group(1))}.{int(m.group(2))}"
            if k not in out or fn.endswith('.svg'):
                out[k] = fn
    return out

SVGS = None

def extract_images(text):
    imgs = {}
    def grab(m):
        imgs[m.group(1)] = (m.group(2), m.group(3))
        return ''
    text = re.sub(r'^\[(image\d+)\]: <data:image/(\w+);base64,([^>]+)>\s*$', grab, text, flags=re.M)
    return text, imgs

def render_figure(num, title, shows, alt, imgref, imgs, chnum):
    global SVGS
    os.makedirs(os.path.join(OUT, 'figures'), exist_ok=True)
    src = None
    if num in SVGS:
        fn = SVGS[num]
        shutil.copy(os.path.join(FIGS, fn), os.path.join(OUT, 'figures', fn))
        src = 'figures/' + fn
    elif imgref and imgref in imgs:
        ext, data = imgs[imgref]
        fn = f"fig-{num.replace('.', '-')}.{ 'png' if ext=='png' else ext}"
        with open(os.path.join(OUT, 'figures', fn), 'wb') as f:
            f.write(base64.b64decode(data))
        src = 'figures/' + fn
    shows = re.sub(r'\s*The final image is in the Final figures folder[^.]*\.', '', shows or '').strip()
    parts = ['<figure class="fig" id="figure-' + num.replace('.', '-') + '">']
    if src:
        parts.append(f'<img src="{src}" alt="{html.escape(alt or title, quote=True)}" loading="lazy">')
    parts.append(f'<figcaption><span class="fignum">Figure {num}</span> {inline(title)}')
    if shows:
        parts.append(f'<span class="figdesc">{inline(shows)}</span>')
    parts.append('</figcaption></figure>')
    return '\n'.join(parts)

def inline(s):
    return markdown.markdown(s).removeprefix('<p>').removesuffix('</p>')

# ---------- quizzes ----------
def parse_questions(block):
    qs = []
    cur = None
    for line in block.split('\n'):
        line = line.rstrip()
        m = re.match(r'^\s*(\d+)\.\s+(.*)$', line)
        o = re.match(r'^\s+([A-D])\.\s+(.*)$', line)
        if m and not o:
            cur = {'n': int(m.group(1)), 'q': m.group(2).strip(), 'opts': []}
            qs.append(cur)
        elif o and cur is not None:
            cur['opts'].append((o.group(1), o.group(2).strip()))
    return qs

def parse_answers(block):
    ans = {}
    cur = None
    for line in block.split('\n'):
        line = line.rstrip()
        m = re.match(r'^\s*(\d+)\.\s+\*\*([A-D])\.\*\*\s*(.*)$', line)
        f = re.match(r'^\s+([A-D]):\s*(.*)$', line)
        if m:
            cur = {'correct': m.group(2), 'fb': {m.group(2): m.group(3).strip()}}
            ans[int(m.group(1))] = cur
        elif f and cur is not None:
            cur['fb'][f.group(1)] = f.group(2).strip()
    return ans

def render_quiz(qs, ans, chnum):
    out = ['<section class="quiz" aria-label="Check questions">',
           '<p class="quiz-intro">Choose an answer to see feedback. Nothing is recorded.</p>']
    for q in qs:
        a = ans.get(q['n'])
        qid = f"q{chnum}-{q['n']}"
        out.append(f'<div class="q" id="{qid}" data-correct="{a["correct"] if a else ""}">')
        out.append(f'<p class="qtext"><span class="qnum">{q["n"]}.</span> {inline(q["q"])}</p><div class="opts">')
        for letter, text in q['opts']:
            fb = (a['fb'].get(letter, '') if a else '')
            fb = re.sub(r'^Correct\.\s*', '', fb)
            out.append(f'<button type="button" class="opt" data-letter="{letter}" data-fb="{html.escape(inline(fb), quote=True)}">'
                       f'<span class="letter">{letter}</span><span class="otext">{inline(text)}</span></button>')
        out.append('</div><div class="fb" aria-live="polite"></div></div>')
    out.append('</section>')
    return '\n'.join(out)

# ---------- chapter ----------
def convert(chnum, text):
    text, imgs = extract_images(text)
    # unwrap Google's blockquoted lists
    text = re.sub(r'^> ?', '', text, flags=re.M)
    # remove bold markers from headings
    text = re.sub(r'^(#{1,6}) \*\*(.+?)\*\*\s*$', r'\1 \2', text, flags=re.M)
    # unescape bold markers inside table cells
    text = text.replace('\\*\\*', '**')

    # figures
    def fig(m):
        return '\n\n' + render_figure(m.group('num'), m.group('title').strip(), m.group('shows'), m.group('alt'),
                                      m.group('img'), imgs, chnum) + '\n\n'
    text = re.sub(
        r'(?:\*?!\[\]\[(?P<img>image\d+)\]\*?\s*\n\s*)?'
        r'\*{1,3}\\\[FIGURE (?P<num>\d+\.\d+): (?P<title>[^\]]+?)\\\]\*{1,3}\s*\n'
        r'(?:\s*\*What it shows: (?P<shows>.*?)\*\s*\n)?'
        r'(?:\s*\*Alt text: (?P<alt>.*?)\*\s*\n)?',
        fig, text)

    # quiz
    quiz_html = ''
    m1 = re.search(r'^## Check questions\s*$', text, flags=re.M)
    m2 = re.search(r'^### Answers and feedback\s*$', text, flags=re.M)
    if m1 and m2:
        qs = parse_questions(text[m1.end():m2.start()])
        ans = parse_answers(text[m2.end():])
        quiz_html = render_quiz(qs, ans, chnum)
        text = text[:m1.start()] + '## Check questions\n\n@@QUIZ@@\n'

    # title + move line
    lines = text.split('\n')
    title = strip_bold_heading(lines[0].lstrip('# ')) if lines[0].startswith('# ') else f'Chapter {chnum}'
    body_md = '\n'.join(lines[1:])
    body = markdown.markdown(body_md, extensions=['tables', 'sane_lists'])
    body = body.replace('<p>@@QUIZ@@</p>', quiz_html)
    # "Move:" line styling
    body = re.sub(r'^<p>(<strong>Move:</strong>.*?)</p>', r'<p class="move">\1</p>', body, count=1, flags=re.S)
    # "At a glance:" label
    body = body.replace('<p><strong>At a glance:</strong></p>', '<p class="glance">At a glance</p>')
    # heading ids + collect h2/h3 for in-page nav
    toc = []
    def hid(m):
        tag, inner = m.group(1), m.group(2)
        i = slug(inner)
        if tag in ('h2', 'h3'):
            toc.append((tag, i, re.sub(r'<[^>]+>', '', inner)))
        return f'<{tag} id="{i}">{inner}</{tag}>'
    body = re.sub(r'<(h[23])>(.*?)</\1>', hid, body)
    # wrap tables for horizontal scroll on phones
    body = body.replace('<table>', '<div class="tablewrap"><table>').replace('</table>', '</table></div>')
    return title, body, toc

# ---------- page shell ----------
CSS_LINK = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,700;1,8..60,400&display=swap" rel="stylesheet"><link rel="stylesheet" href="style.css">'

def shell(page_title, nav_html, main_html, current=None):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)}</title>
{CSS_LINK}
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="top">
  <button class="navtoggle" type="button" aria-controls="sidebar" aria-expanded="false">Contents</button>
  <a class="booktitle" href="index.html">{BOOK}</a>
</header>
<div class="layout">
<nav id="sidebar" class="sidebar" aria-label="Chapters">
{nav_html}
</nav>
<main id="content" class="content">
{main_html}
</main>
</div>
<script src="site.js"></script>
</body>
</html>'''

def sidebar(chs, current):
    items = ['<ol class="chlist">']
    for n, t, fn in chs:
        short = re.sub(r'^Chapter \d+:\s*', '', t)
        cls = ' class="current" aria-current="page"' if n == current else ''
        items.append(f'<li><a href="{fn}"{cls}><span class="n">{n}</span> {html.escape(short)}</a></li>')
    items.append('</ol>')
    return '\n'.join(items)

def main():
    global SVGS
    if os.path.exists(OUT):
        for x in os.listdir(OUT):
            if x == '.git':
                continue
            p = os.path.join(OUT, x)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(OUT, exist_ok=True)
    SVGS = figure_files()
    raw = load_chapters()
    built = []
    for n, text in raw:
        title, body, toc = convert(n, text)
        built.append((n, title, f'chapter-{n:02d}.html', body, toc))
    meta = [(n, t, fn) for n, t, fn, _, _ in built]
    for i, (n, title, fn, body, toc) in enumerate(built):
        prev_ = built[i - 1] if i > 0 else None
        next_ = built[i + 1] if i + 1 < len(built) else None
        pager = ['<nav class="pager" aria-label="Chapter navigation">']
        pager.append(f'<a class="prev" href="{prev_[2]}"><span>Previous</span>{html.escape(prev_[1])}</a>' if prev_ else '<span></span>')
        pager.append(f'<a class="next" href="{next_[2]}"><span>Next</span>{html.escape(next_[1])}</a>' if next_ else '<span></span>')
        pager.append('</nav>')
        onpage = ''
        h2s = [t for t in toc if t[0] == 'h2']
        if h2s:
            onpage = '<details class="onpage"><summary>In this chapter</summary><ul>' + ''.join(
                f'<li class="{tag}"><a href="#{i_}">{html.escape(txt)}</a></li>' for tag, i_, txt in toc) + '</ul></details>'
        main_html = f'<article class="chapter"><h1>{html.escape(title)}</h1>\n{onpage}\n{body}\n</article>\n' + '\n'.join(pager)
        with open(os.path.join(OUT, fn), 'w', encoding='utf-8') as f:
            f.write(shell(f'{title} | {BOOK}', sidebar(meta, n), main_html))
    # index
    rows = '\n'.join(f'<li><a href="{fn}"><span class="n">{n}</span><span class="t">{html.escape(re.sub(r"^Chapter \d+:\s*", "", t))}</span></a></li>' for n, t, fn in meta)
    index_main = f'''<section class="cover">
<p class="eyebrow">An open textbook</p>
<h1>{BOOK}</h1>
<p class="lede">An introduction to building, answering and weighing arguments, from everyday decisions to federal policy. Each chapter ends with check questions you can answer for instant feedback.</p>
<p class="edition">Paul Villa, Diablo Valley College · {EDITION}</p>
<p><a class="start" href="{meta[0][2]}">Start reading</a></p>
</section>
<section class="toc"><h2>Chapters</h2><ol class="tocgrid">{rows}</ol></section>'''
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(shell(BOOK, sidebar(meta, None), index_main))
    here = os.path.dirname(os.path.abspath(__file__))
    for asset in ('style.css', 'site.js'):
        shutil.copy(os.path.join(here, asset), os.path.join(OUT, asset))
    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    report = {n: {'title': t, 'figures': body.count('<figure'), 'quiz': body.count('class="q"')} for n, t, _, body, _ in built}
    print(json.dumps(report, indent=0))

main()
