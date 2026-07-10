import os, io
target = None
for f in os.listdir('.'):
    if '专报' in f and '20260626' in f and f.endswith('.md'):
        target = f; break
lines = io.open(target, encoding='utf-8-sig').read().splitlines()
entries = []
cur = None; bl = []
for raw in lines:
    s = raw.strip()
    if s.startswith('##') and '｜' in s and s.count('｜') >= 3:
        if cur: cur['body'] = '\n'.join(bl).strip()
        rest = s[2:].strip(); parts = [x.strip() for x in rest.split('｜')]
        if len(parts) >= 4: cur = {'title': parts[3], 'body': ''}; entries.append(cur); bl = []; continue
    if cur and s and not s.startswith('---'): bl.append(s)
if cur: cur['body'] = '\n'.join(bl).strip()
for i, e in enumerate(entries, 1):
    bt = e['body'].replace('\n','').replace(' ','')
    ok = 'OK' if 1000 <= len(bt) <= 1100 else 'ADJUST'
    print(str(i) + ' total=' + str(len(bt)) + ' ' + ok + ' ' + e['title'][:35])
