#!/usr/bin/env python3
"""Static GitHub Pages renderer. Reads docs without modifying source."""
from pathlib import Path
import html, re, shutil
import mistune
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_site'; DOCS=ROOT/'docs'
if OUT.exists():shutil.rmtree(OUT)
OUT.mkdir()
css='*{box-sizing:border-box}body{margin:0;background:#f6f5ef;color:#27372e;font:16px/1.7 system-ui,sans-serif}header{background:#263f33;color:#f7f8ed;padding:1.3rem max(5vw,1rem)}header a{color:#e2ebda}main{max-width:1150px;margin:2rem auto;padding:0 1.4rem}h1,h2,h3{line-height:1.25}h1{font:2.4rem Georgia,serif}a{color:#466747}nav{display:flex;gap:1rem;flex-wrap:wrap}section,.page{background:white;padding:1.5rem 2rem;margin:1rem 0;border:1px solid #e1e5dc;border-radius:.8rem}table{border-collapse:collapse;display:block;overflow-x:auto}th,td{border:1px solid #dce2d7;padding:.45rem .7rem;text-align:left}th{background:#eef2e8}pre{overflow:auto;padding:1rem;background:#edf1eb}code{overflow-wrap:anywhere}img{max-width:100%;height:auto}.notice{border-left:4px solid #9f7948;padding:1rem;background:#fbf3e1}li{margin:.2rem 0}footer{padding:2rem;color:#6a716b}'
(OUT/'style.css').write_text(css)
markdown=mistune.create_markdown(plugins=['table','strikethrough'])
entries=[('Character Design Brief','Myca Character Design Brief.md'),('Master Character Prompt','Myca Master Character Prompt.md'),('Locomotion Reference','Myca Locomotion Reference.md'),('Prompt Modules','Production/Prompt Modules and Style Translation.md'),('Reference Index','References/Reference Index.md'),('Canon Shortlist','References/Definitive Canon Shortlist.md'),('Resource README','README.md')]
def wrap(title,body,root_relative=''):
  # links in source markdown point to original relative folder; preserve through mirrored output paths
  nav='<nav><a href="'+root_relative+'index.html">Overview</a><a href="'+root_relative+'Myca Resource Guide.html">Original visual guide</a><a href="'+root_relative+'docs/Myca Character Design Brief.html">Character design</a><a href="'+root_relative+'docs/References/Reference Index.html">References</a></nav>'
  return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' · Myca Cellium</title><link rel="stylesheet" href="'+root_relative+'style.css"></head><body><header><strong>MYCA CELLIUM · CANON REFERENCE</strong>'+nav+'</header><main><article class="page">'+body+'</article></main><footer>Character continuity first · Source details remain feature-scoped</footer></body></html>'
for md in DOCS.rglob('*.md'):
  relative=md.relative_to(DOCS)
  dest=OUT/'docs'/relative.with_suffix('.html')
  dest.parent.mkdir(parents=True,exist_ok=True)
  # Keep original .md hyperlinks working by shipping the source docs and avoid broken links to non-imported images.
  content=md.read_text(encoding='utf-8')
  rendered=markdown(content)
  rendered=re.sub(r'href="([^"]+)\.md(#[^"]*)?"', lambda m:'href="'+m.group(1)+'.html'+(m.group(2) or '')+'"',rendered)
  depth=len(dest.relative_to(OUT).parts)-1
  dest.write_text(wrap(md.stem,rendered,'../'*depth),encoding='utf-8')
shutil.copytree(DOCS,OUT/'source',dirs_exist_ok=True)
# Also copy original files into mirrored docs/ paths, so direct links to original sources work where present.
shutil.copytree(DOCS,OUT/'docs',dirs_exist_ok=True)
shutil.copy2(DOCS/'Myca Resource Guide.html',OUT/'Myca Resource Guide.html')
links=''.join('<li><a href="docs/'+path[:-3]+'.html">'+html.escape(name)+'</a></li>' for name,path in entries)
body='<h1>Myca · Character Design Library</h1><p>A browsable source-of-truth for an evolving fungal character. Canon changes require explicit creator approval; reference art controls only documented features.</p><p class="notice"><strong>Partial source import:</strong> The original image directory, acting guide, review checklist and decision log were not in this attachment set. The preserved visual guide contains embedded previews; its links to missing original files will remain incomplete.</p><h2>Documentation</h2><ul>'+links+'</ul><h2>Visual overview</h2><p><a href="Myca Resource Guide.html">Open preserved, illustrated browser edition</a> (large embedded-preview HTML).</p><h2>Design statuses</h2><p>Current baseline is 1.0. Seven living-membrane variants remain experiments, not replacements for the documented pink skirt and dark waistband.</p>'
(OUT/'index.html').write_text(wrap('Library',body),encoding='utf-8')
print('Built',OUT)
