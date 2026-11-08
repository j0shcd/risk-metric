"""Bounded offline H41 extraction. No original-vintage/PIT certification."""
import datetime as dt
import re
from html.parser import HTMLParser

TITLE='Consolidated Statement of Condition of All Federal Reserve Banks'
DATE=r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*\d{4}'
class ExtractionError(ValueError): pass

def clean(s):return ' '.join(s.replace('\xa0',' ').split())
def date(s):
 s=clean(s)
 for fmt in ('%b %d, %Y','%B %d, %Y'):
  try:return dt.datetime.strptime(s,fmt).date()
  except ValueError:pass
 raise ExtractionError('invalid date')
def integer(s):
 s=clean(s)
 if not re.fullmatch(r'(?:[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*)',s):raise ExtractionError('invalid positive integer assets')
 return int(s.replace(',',''))
class Node:
 def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[];self.prefix=''
 def text(self):return ''.join(c if isinstance(c,str) else c.text()+ ('\n' if c.tag in ('p','br','div','tr') else '') for c in self.children)
 def descendants(self,tag):
  for c in self.children:
   if isinstance(c,Node):
    if c.tag==tag:yield c
    yield from c.descendants(tag)
class Reader(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root];self.previous=[];self.count=0
 def handle_starttag(self,tag,attrs):
  self.count+=1
  if self.count>100000:raise ExtractionError('too many tags')
  node=Node(tag,attrs);node.prefix=''.join(self.previous[-200:]);self.stack[-1].children.append(node)
  if tag in ('br','p','div'):self.previous.append('\n')
  if tag not in ('br','hr','img','meta','link','input','wbr','area','base','embed','param','source'):self.stack.append(node)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==tag:self.stack=self.stack[:i];break
  if tag in ('p','div','tr','pre','table'):self.previous.append('\n')
 def handle_data(self,s):self.stack[-1].children.append(s);self.previous.append(s)

def pre_extract(text):
 matches=list(re.finditer(r'^\s*\d+\.\s*'+re.escape(TITLE)+r'\s*$',text,re.M));out=[]
 for match in matches:
  tail=text[match.end():];end=re.search(r'^\s*\d+\.\s+\S',tail,re.M)
  section=tail[:end.start()] if end else tail
  lines=section.splitlines();nonempty=[x for x in lines if x.strip()]
  if not nonempty or clean(nonempty[0])!='Millions of dollars':raise ExtractionError('pre units')
  header=next((i for i,l in enumerate(lines) if 'Assets, liabilities, and capital' in l),None)
  if header is None:raise ExtractionError('pre header missing')
  heading=lines[header]
  if re.fullmatch(r'\s*Assets, liabilities, and capital\s+Eliminations\s+Wednesday\s+Change since\s*',heading):
   if header+2>=len(lines):raise ExtractionError('pre incomplete header')
   a=re.fullmatch(r'\s*from\s+('+DATE+r')\s+Wednesday\s+Wednesday\s*',lines[header+1])
   b=re.fullmatch(r'\s*consolidation\s+('+DATE+r')\s+('+DATE+r')\s*',lines[header+2])
   if not a or not b:raise ExtractionError('pre dated columns')
   obs=date(a[1]);priors=[date(b[1]),date(b[2])]
  elif header>=2 and re.fullmatch(r'\s*Eliminations from\s+Wednesday\s+Change since\s*',lines[header-2]):
   a=re.fullmatch(r'\s*consolidation\s+('+DATE+r')\s+Wednesday\s+Wednesday\s*',lines[header-1])
   b=re.fullmatch(r'\s*Assets, liabilities, and capital\s+('+DATE+r')\s+('+DATE+r')\s*',heading)
   if not a or not b:raise ExtractionError('pre alternate dated columns')
   obs=date(a[1]);priors=[date(b[1]),date(b[2])]
  else:
   # Older release layout has the same columns across three differently wrapped lines.
   if header<2 or not re.fullmatch(r'\s*Eliminations\s+Change since\s*',lines[header-2]) or not re.fullmatch(r'\s*from\s+Wednesday\s+Wednesday\s+Wednesday\s*',lines[header-1]):raise ExtractionError('pre column sequence')
   a=re.fullmatch(r'\s*Assets, liabilities, and capital\s+consolidation\s+('+DATE+r')\s+('+DATE+r')\s+('+DATE+r')\s*',heading)
   if not a:raise ExtractionError('pre older dated columns')
   obs=date(a[1]);priors=[date(a[2]),date(a[3])]
  if not all(d<obs and d.weekday()==2 for d in priors):raise ExtractionError('prior columns must be earlier Wednesdays')
  targets=[l for l in lines if re.match(r'^\s*Total assets\s',l)]
  if len(targets)!=1:raise ExtractionError('pre duplicate/missing target')
  # Exact documented sequence: optional elimination, current level, two changes.
  row=re.fullmatch(r'\s*Total assets\s+(?:\(\d[\d,]*\)\s+)?([\d,]+)\s+([+-]\s*[\d,]+|0)\s+([+-]\s*[\d,]+|0)\s*',targets[0])
  if not row:raise ExtractionError('pre numeric columns')
  out.append((obs,integer(row[1]),'pre_fixed_columns',clean(heading)))
 return out

def html_extract(table):
 prefix=table.prefix
 # Scope strictly to the immediately preceding title and units, not mentions in notes.
 if not re.search(r'\d+\.\s*'+re.escape(TITLE)+r'\s+Millions\s+of dollars\s*$',prefix):return None
 grid=[];occupied={};origins={};physical=[]
 for ri,tr in enumerate(table.descendants('tr')):
  row={c:v for (r,c),v in occupied.items() if r==ri};col=0;cells=[]
  for cell in tr.children:
   if not isinstance(cell,Node) or cell.tag not in ('td','th'):continue
   while col in row:col+=1
   try:rs=int(cell.attrs.get('rowspan',1));cs=int(cell.attrs.get('colspan',1))
   except ValueError:raise ExtractionError('bad span')
   if not 1<=rs<=20 or not 1<=cs<=20:raise ExtractionError('unbounded span')
   value=clean(cell.text());cells.append((col,rs,cs))
   for rr in range(ri,ri+rs):
    for cc in range(col,col+cs):
     if (rr,cc) in occupied:raise ExtractionError('overlapping cells')
     occupied[rr,cc]=value;origins[rr,cc]=(ri,col)
     if rr==ri:row[cc]=value
   col+=cs
  grid.append(row);physical.append(cells)
 targets=[i for i,r in enumerate(grid) if r.get(0)=='Total assets']
 if len(targets)!=1:raise ExtractionError('HTML duplicate/missing target')
 target=targets[0];headers=[]
 if physical[target]!=[(i,1,1) for i in range(5)] or set(grid[target])!=set(range(5)) or len({origins[target,i] for i in range(5)})!=5:raise ExtractionError('target requires five distinct unspanned physical cells')
 header_end=next((i for i,r in enumerate(grid[:target]) if r.get(0)=='Assets'),None)
 if header_end is None or any(set(r)!=set(range(5)) for r in grid[:header_end]):raise ExtractionError('header must cover exactly five columns')
 for c in range(max(grid[target])+1):
  vals=[]
  for r in grid[:header_end]:
   v=r.get(c,'')
   if v and (not vals or vals[-1]!=v):vals.append(v)
   if r.get(0)=='Assets':break
  headers.append(clean(' '.join(vals)))
 candidates=[]
 for c,h in enumerate(headers):
  m=re.fullmatch(r'Wednesday\s+('+DATE+r')',h)
  if m:candidates.append((c,date(m[1])))
 if len(candidates)!=1:raise ExtractionError('HTML current Wednesday column ambiguous')
 c,obs=candidates[0]
 if c!=2 or headers[0]!='Assets, liabilities, and capital' or headers[1]!='Eliminations from consolidation':raise ExtractionError('HTML column scope')
 priors=[]
 for h in headers[3:5]:
  prior=re.fullmatch(r'Change since Wednesday\s+('+DATE+r')',h)
  if not prior:raise ExtractionError('HTML prior column scope')
  priors.append(date(prior[1]))
 if len(priors)!=2 or not all(d<obs and d.weekday()==2 for d in priors):raise ExtractionError('prior columns must be earlier Wednesdays')
 return obs,integer(grid[target][c]),'html_spanned_columns',headers[c]

def extract(raw,expected_release):
 if not isinstance(raw,bytes) or len(raw)>4*1024*1024:raise ExtractionError('bounded bytes required')
 try:expected=dt.date.fromisoformat(expected_release);text=raw.decode('utf-8-sig')
 except (ValueError,UnicodeError):raise ExtractionError('invalid input encoding/date')
 reader=Reader();reader.feed(text);plain=reader.root.text()
 releases=re.findall(r'Release Date:\s*(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*)?('+DATE+r')',plain)
 if len(releases)!=1 or date(releases[0])!=expected:raise ExtractionError('release date missing/duplicate/mismatch')
 candidates=[]
 for pre in reader.root.descendants('pre'):candidates.extend(pre_extract(pre.text()))
 for table in reader.root.descendants('table'):
  found=html_extract(table)
  if found:candidates.append(found)
 if len(candidates)!=1:raise ExtractionError('missing/ambiguous consolidated target')
 obs,value,mode,header=candidates[0]
 if obs.weekday()!=2 or not 0<=(expected-obs).days<=7:raise ExtractionError('observation must be Wednesday within seven days of release')
 return {'release_date':expected.isoformat(),'observation_date':obs.isoformat(),'total_assets_usd_millions':value,'extraction_mode':mode,'evidence':{'table_title':TITLE,'row':'Total assets','unit':'Millions of dollars','column':header},'originality':'not_asserted','pit':'not_asserted'}
