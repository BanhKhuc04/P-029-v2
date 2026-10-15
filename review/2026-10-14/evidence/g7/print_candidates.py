import json
from collections import defaultdict

data = json.load(open('review/2026-10-14/evidence/g7/candidate-findings.json', encoding='utf-8'))
by_rule = defaultdict(list)
for d in data:
    by_rule[d['rule']].append(d)

for idx, d in enumerate(by_rule['fit.outside'], 1):
    print(f"fit.outside {idx}. [{d['scene']} frame={d['frame']} track={d['track_id']} {d['label']} {d['severity']}] {d['message']}")
