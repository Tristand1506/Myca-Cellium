#!/usr/bin/env python3
"""Deterministic integrity checks. No speculative visual/canon approval."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def fail(msg): errors.append(msg)
reg=json.loads((ROOT/'data/canon-register.json').read_text(encoding='utf-8'))
ids=set()
for item in reg['records']:
    name=item['id']
    if name in ids: fail(f'Duplicate canon ID: {name}')
    ids.add(name)
    if item['status'] not in ('canon','provisional','experimental','unresolved','superseded','rejected','style-specific'): fail(f'Invalid status: {name}')
    path=ROOT/item['authority']
    if not path.is_file(): fail(f'Missing authority file for {name}: {path}')
    elif item.get('section') and item['section'].lower() not in path.read_text(encoding='utf-8').lower(): fail(f'Section not found for {name}: {item["section"]}')
text=(ROOT/'PROJECT_INSTRUCTIONS.md').read_text(encoding='utf-8')
if len(text)>8000: fail(f'Project instructions exceed 8000 characters: {len(text)}')
if len({x['id'] for x in reg['records']}) != len(reg['records']): fail('Duplicate IDs')
refs=(ROOT/'docs/References/Reference Index.md').read_text(encoding='utf-8')
for r in ['R08','R11','R20','R28','R30','R32','R33','R34']:
    if r not in refs: fail(f'Expected reference absent: {r}')
for e in errors: print('ERROR:',e,file=sys.stderr)
print(f'Validated {len(reg["records"])} feature records; Project Instructions: {len(text)} characters; {len(errors)} errors')
sys.exit(bool(errors))
