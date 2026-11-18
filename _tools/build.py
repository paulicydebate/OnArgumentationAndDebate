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
    # mapped blocks (lines joined by soft breaks, each starting with a bold label) become panels
    body = re.sub(r'<p>(<strong>[^<]{1,40}:</strong>(?:(?!</p>).)*?<br />(?:(?!</p>).)*)</p>', r'<p class="panel">\1</p>', body, flags=re.S)
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

ALIAS={'extra-topicality':['extra-topical'],'effects topicality':['effects topical'],'rehighlighting':['rehighlight','rehighlighted'],
 'the scale':['Scale'],'dropped argument':['dropped','drops'],'top down':['top-down','from the top down','top'],'forensics':['forensic'],
 'directional uniqueness':['directional'],'terminal impact':['terminal'],'linear impact':['linear'],'algebraic analysis':['Algebraic Analysis']}
DEFWORDS=re.compile(r"\b(is|are|means|was|refers|argues|happens|asks|describes|explains|has|have|gives|pits|uses|called|call)\b|:|—|, an? ")
def plain(s): return html.unescape(re.sub(r'<[^>]+>','',s))
def split_sents(t): return re.split(r"(?:(?<=[.!?])|(?<=[.!?][\"”]))\s+(?=[A-Z\"“\[])",t)
def extract(n, page):
    m=re.search(r'<h2 id="key-terms">.*?</h2>\s*<p>(.*?)</p>',page,re.S)
    if not m: return [],[]
    kt=[t.strip().rstrip('.') for t in plain(m.group(1)).split(',') if t.strip()]
    start=m.end(); body=page[start:]
    stop=re.search(r'<h2 id="check-questions"',body)
    body=body[:stop.start()] if stop else body
    heads=[(h.start(),h.group(1)) for h in re.finditer(r'<h[23] id="([^"]+)"',body)]
    out=[];miss=[]
    for t in kt:
        names=[t]+ALIAS.get(t.lower(),[])
        hit=None;bold=True
        for nm in names:
            pat=re.compile(r'<strong>((?:the )?'+re.escape(nm)+r'(?:s|es)?[.:]?)</strong>',re.I)
            for pm in re.finditer(r'<(p|li|td)[^>]*>(.*?)</\1>',body,re.S):
                if pat.search(pm.group(2)): hit=(pm,pat);break
            if hit: break
        if not hit:
            for nm in names:
                pat=re.compile(r'\b('+re.escape(nm)+r'(?:s|es)?)\b',re.I)
                for pm in re.finditer(r'<(p|li)[^>]*>(.*?)</\1>',body,re.S):
                    if pat.search(plain(pm.group(2))): hit=(pm,pat);bold=False;break
                if hit: break
        if not hit: miss.append(t); continue
        pm,pat=hit
        txt=pm.group(2)
        txt=re.sub(r'<strong>(.*?)</strong>',lambda x:'[['+x.group(1)+']]',txt) if bold else txt
        txt=plain(txt).replace('\n',' ')
        sents=split_sents(txt)
        key=(lambda x: re.search(r'\[\[(?:the )?'+'|'.join(re.escape(z) for z in names)+r'(?:s|es)?[.:]?\]\]',x,re.I)) if bold else (lambda x: pat.search(x))
        i=next((k for k,x in enumerate(sents) if key(x)),0)
        d=sents[i]
        if len(d.split())<6 or not DEFWORDS.search(d):
            if i+1<len(sents): d=d+' '+sents[i+1]
            elif i>0: d=sents[i-1]+' '+d
        sec=None
        for p,h in heads:
            if p<pm.start(): sec=h
        out.append({'term':t,'ch':n,'sec':sec,'def':d,'bold':bold})
    return out,miss


# ---------- glossary ----------
GLOSS_OVERRIDE = {
 ('the scale', 4): "The picture this book uses for how a judge decides: each argument a side wins goes on its side of a balance, arguments that cancel come off both sides, and the heavier side wins. If the Scale is level or empty, the judge votes on presumption.",
 ('four-step refutation', 4): "A four-part answer to an argument: say which argument you are answering, state your answer, support it, and explain what it means for the debate (\"They say... We say... Based on... That means...\").",
 ('delivery', 5): "How you present an argument out loud. In a debate, your own delivery is the biggest source of noise you control: an argument the judge cannot flow does not count.",
 ('the four moves', 21): "The four skills this book is organized around: build an argument, prove it with evidence, answer the other side, and weigh what you won against what you lost.",
 ('affirmative flexibility', 16): "The affirmative's standard that it needs room to be creative, because the negative can read almost any argument against any plan while the affirmative is bound by the resolution. Unexpected plans are good for debate as long as they stay inside the resolution.",
 ('negative', 1): "The side that argues the resolution should not be accepted. Other formats call the sides government and opposition, or pro and con.",
 ('rebuttal', 1): "A later speech in which debaters may not make new arguments, except to answer something new from the speech just before.",
 ('rehighlighting', 9): "Reading different words from an opponent's card to make the same paragraph say something else, often the opposite. A card that can be rehighlighted against you is worse than a weak card.",
 ('pit of doom', 11): "A cross-examination question where one answer clearly gives you access to an argument you are likely to make. Unlike the fork, it needs only one answer to help you.",
 ('terminal impact', 14): "An impact that ends in harm to people, such as lost lives, poverty or loss of rights, rather than a step along the way.",
}
GLOSS_EXTRA_ALIAS = {'flow': ['Flowing'], 'the scale': ['Scale']}

def gloss_clean(d, term):
    # a bold label at the start that is not the term ("The sides.") is dropped
    m = re.match(r'^\[\[([^\]]+)\]\]\s*', d)
    if m:
        lab = m.group(1).rstrip('.:').lower()
        lab = re.sub(r'^the ', '', lab)
        t = re.sub(r'^the ', '', term.lower())
        if not (lab.startswith(t) or t.startswith(lab)):
            d = d[m.end():]
        elif m.group(1).endswith(('.', ':')) and len(d[m.end():].split()) > 0 and d[m.end():][:1].isupper():
            d = d[m.end():]
    d = html.escape(d.strip(), quote=False)
    d = re.sub(r'\[\[(.*?)\]\]', r'<strong>\1</strong>', d)
    return d

def build_glossary(built):
    for k, v in GLOSS_EXTRA_ALIAS.items():
        ALIAS.setdefault(k, []).extend(v)
    entries = []
    for n, title, fn, body, toc in built:
        page = body
        out, miss = extract(n, page)
        for e in out:
            e['fn'] = fn
        entries += out
    # overrides
    for e in entries:
        key = (e['term'].lower(), e['ch'])
        if key in GLOSS_OVERRIDE:
            e['def'] = GLOSS_OVERRIDE[key]; e['bold'] = True; e['override'] = True
    have_bold = {e['term'].lower() for e in entries if e['bold']}
    keep = [e for e in entries if e['bold'] or e['term'].lower() not in have_bold]
    groups = {}
    for e in keep:
        groups.setdefault(e['term'].lower(), []).append(e)
    def sortkey(t): return re.sub(r'^the ', '', t)
    letters = {}
    for t in sorted(groups, key=sortkey):
        letters.setdefault(sortkey(t)[0].upper(), []).append(t)
    parts = ['<article class="chapter glossary"><h1>Glossary</h1>',
             '<p class="lede-small">Every key term in the book, defined in the words of the chapter that introduces it. Select a chapter link to read the term in context.</p>',
             '<input type="search" id="gfilter" class="gfilter" placeholder="Filter terms" aria-label="Filter glossary terms">',
             '<nav class="letters" aria-label="Jump to letter">' + ''.join(f'<a href="#letter-{L}">{L}</a>' for L in letters) + '</nav>']
    for L, terms in letters.items():
        parts.append(f'<section class="gletter" id="letter-{L}"><h2>{L}</h2><dl>')
        for t in terms:
            es = groups[t]
            disp = es[0]['term']; disp = disp[0].upper() + disp[1:]
            parts.append(f'<div class="gentry" id="term-{slug(t)}"><dt>{html.escape(disp)}</dt>')
            for e in es:
                d = e['def'] if e.get('override') else gloss_clean(e['def'], e['term'])
                href = e['fn'] + (('#' + e['sec']) if e.get('sec') else '')
                parts.append(f'<dd>{d} <a class="gref" href="{href}">Chapter {e["ch"]}</a></dd>')
            parts.append('</div>')
        parts.append('</dl></section>')
    parts.append('</article>')
    return '\n'.join(parts), keep

# ---------- search index ----------
def search_records(built, gloss):
    recs = []
    for n, title, fn, body, toc in built:
        b = re.sub(r'<section class="quiz".*?</section>', '', body, flags=re.S)
        b = re.sub(r'<figure.*?</figure>', lambda m: ' ' + re.sub(r'<[^>]+>', ' ', m.group(0)) + ' ', b, flags=re.S)
        heads = list(re.finditer(r'<(h[23]) id="([^"]+)">(.*?)</\1>', b))
        cuts = [(0, '', 'Introduction')] + [(h.start(), h.group(2), re.sub(r'<[^>]+>', '', h.group(3))) for h in heads]
        for i, (pos, sid, stitle) in enumerate(cuts):
            end = cuts[i + 1][0] if i + 1 < len(cuts) else len(b)
            seg = re.sub(r'</?(strong|em|b|i|a|span|mark|sup|sub|code)\b[^>]*>', '', b[pos:end])
            txt = html.unescape(re.sub(r'<[^>]+>', ' ', seg))
            txt = re.sub(r'\s+', ' ', txt).strip()
            if stitle and txt.startswith(stitle):
                txt = txt[len(stitle):].strip()
            if sid in ('check-questions', 'key-terms') or len(txt) < 20:
                continue
            recs.append({'c': n, 't': re.sub(r'^Chapter \d+:\s*', '', title), 's': stitle, 'u': fn + ('#' + sid if sid else ''), 'x': txt})
    for e in gloss:
        d = e['def'] if e.get('override') else re.sub(r'<[^>]+>', '', gloss_clean(e['def'], e['term']))
        recs.append({'c': 0, 't': 'Glossary', 's': e['term'], 'u': 'glossary.html#term-' + slug(e['term'].lower()), 'x': html.unescape(d)})
    return recs

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
  <div class="search" role="search">
    <input type="search" id="q" placeholder="Search the book" aria-label="Search the book" autocomplete="off">
    <div id="results" class="results" hidden></div>
  </div>
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
    cls = ' class="current" aria-current="page"' if current == 'glossary' else ''
    items.append(f'<ul class="chlist extra"><li><a href="glossary.html"{cls}><span class="n">&#9670;</span> Glossary</a></li></ul>')
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
    # glossary
    gl_html, gl_entries = build_glossary(built)
    with open(os.path.join(OUT, 'glossary.html'), 'w', encoding='utf-8') as f:
        f.write(shell(f'Glossary | {BOOK}', sidebar(meta, 'glossary'), gl_html))
    # search index
    with open(os.path.join(OUT, 'search-index.json'), 'w', encoding='utf-8') as f:
        json.dump(search_records(built, gl_entries), f, ensure_ascii=False, separators=(',', ':'))
    # index
    rows = '\n'.join(f'<li><a href="{fn}"><span class="n">{n}</span><span class="t">{html.escape(re.sub(r"^Chapter \d+:\s*", "", t))}</span></a></li>' for n, t, fn in meta)
    index_main = f'''<section class="cover">
<p class="eyebrow">An open textbook</p>
<h1>{BOOK}</h1>
<p class="lede">An introduction to building, answering and weighing arguments, from everyday decisions to federal policy. Each chapter ends with check questions you can answer for instant feedback.</p>
<p class="edition">Paul Villa, Diablo Valley College · {EDITION}</p>
<p><a class="start" href="{meta[0][2]}">Start reading</a></p>
</section>
<section class="toc"><h2>Chapters</h2><ol class="tocgrid">{rows}</ol><p class="glink"><a href="glossary.html">Glossary of key terms</a></p></section>'''
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(shell(BOOK, sidebar(meta, None), index_main))
    here = os.path.dirname(os.path.abspath(__file__))
    for asset in ('style.css', 'site.js'):
        shutil.copy(os.path.join(here, asset), os.path.join(OUT, asset))
    open(os.path.join(OUT, '.nojekyll'), 'w').close()
    print('glossary entries:', len(gl_entries))
    report = {n: {'title': t, 'figures': body.count('<figure'), 'quiz': body.count('class="q"')} for n, t, _, body, _ in built}
    print(json.dumps(report, indent=0))

main()
