import os, re, io, sys

target_dir = sys.argv[1]
os.chdir(target_dir)

# find the入册 file: longer filename with 专报
files = [x for x in os.listdir('.') if x.endswith('.md') and '20260626' in x]
report = None
excerpt = None
for f in files:
    if len(f) > 20:
        report = f
    else:
        excerpt = f

def count_body(text):
    """Count total chars in body paragraphs (between ## headers, excluding front matter)."""
    entries = []
    cur = None
    bl = []
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith('## ') and len(s) > 10:
            if cur:
                cur['body'] = '\n'.join(bl).strip()
            rest = s[3:]
            parts = [x.strip() for x in re.split('[|]', rest)]
            title = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else '')
            cur = {'media': parts[1], 'title': title, 'body': ''}
            entries.append(cur)
            bl = []
            continue
        if cur and s and not s.startswith('---'):
            bl.append(s)
    if cur:
        cur['body'] = '\n'.join(bl).strip()
    return entries

def count_excerpt(text):
    """Count total chars per numbered item."""
    items = re.findall(r'\d+\..+?(?=\n\d+\.\s|\Z)', text, re.DOTALL)
    results = []
    for item in items:
        clean = item.replace('\n', '').replace(' ', '').strip()
        results.append(clean)
    return results

if report:
    t = io.open(report, encoding='utf-8-sig').read()
    entries = count_body(t)
    for i, e in enumerate(entries, 1):
        bt = e['body'].replace('\n', '').replace(' ', '')
        print('%d | total=%d | %s' % (i, len(bt), e['title']))

if excerpt:
    t = io.open(excerpt, encoding='utf-8-sig').read()
    items = count_excerpt(t)
    for i, item in enumerate(items, 1):
        print('excerpt %d | total=%d' % (i, len(item)))
