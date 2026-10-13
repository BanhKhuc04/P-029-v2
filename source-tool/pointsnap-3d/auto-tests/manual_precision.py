"""Summarize existing human verdicts without creating labels or certifying G7."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

VERDICTS = {'Đúng lỗi':'true', 'Báo nhầm':'false', 'Không rõ':'unknown', 'Không chắc':'unknown', '':'unreviewed'}


def summarize(path):
    groups = defaultdict(list)
    seen = {}
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'scene','frame','track_id','label','rule','verdict'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV missing review identity or verdict columns')
        for row in reader:
            verdict = row['verdict'].strip()
            if verdict not in VERDICTS:
                raise ValueError('Unknown human verdict')
            key = tuple(row[k] for k in ('scene','frame','track_id','label','rule'))
            if key in seen:
                if seen[key] != verdict:
                    raise ValueError('Conflicting verdicts for one finding')
                continue
            seen[key] = verdict
            groups[row['rule']].append(row)
    rules = {}
    for rule, rows in sorted(groups.items()):
        counts = Counter(VERDICTS[r['verdict'].strip()] for r in rows)
        decided = counts['true'] + counts['false']
        rules[rule] = dict(counts={k:counts[k] for k in ('true','false','unknown','unreviewed')},
                          precision=counts['true']/decided if decided else None,
                          decided_findings=decided,
                          decided_tracks=len({(r['scene'],r['track_id'],r['label']) for r in rows
                                              if VERDICTS[r['verdict'].strip()] in ('true','false')}))
    return dict(source=str(path), rules=rules, g7_status='UNASSESSED',
                reason='Descriptive existing verdicts only; sample scope, independent split and coverage need review')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verdicts', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.verdicts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
