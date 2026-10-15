"""Verify CVAT task 18 labels and attributes."""
import json
import httpx
from pathlib import Path

def main():
    headers = {
        'Authorization': 'Bearer yso6BsQJ.7S28RZNe7aKRZ1FA6M6scCcWH6iMzcpS',
        'Accept': 'application/vnd.cvat+json'
    }
    r = httpx.get('http://localhost:8080/api/tasks/18', headers=headers)
    assert r.status_code == 200, f"Failed to get task: {r.status_code}"
    task_data = r.json()

    rj = httpx.get('http://localhost:8080/api/jobs?task_id=18', headers=headers)
    jobs_data = rj.json().get('results', [])

    rl = httpx.get('http://localhost:8080/api/labels?task_id=18', headers=headers)
    labels_data = rl.json().get('results', [])

    print('Task ID:', task_data['id'])
    print('Task Name:', task_data['name'])
    print('Jobs:', [(j['id'], j['stage'], j['state']) for j in jobs_data])
    print('Labels count:', len(labels_data))
    
    label_names = [l['name'] for l in labels_data]
    print('Labels:', label_names)

    expected_classes = ["Vehicle", "Two-wheels", "Pedestrian", "Animal", "Obstacle"]
    assert set(label_names) == set(expected_classes), f"Mismatch classes: {label_names} vs {expected_classes}"

    for l in labels_data:
        attrs = {a['name']: {'type': a['input_type'], 'values': a['values'], 'mutable': a['mutable']} for a in l['attributes']}
        print(f"  Class: {l['name']}")
        for aname, ainfo in attrs.items():
            print(f"    - {aname}: {ainfo['type']}, mutable={ainfo['mutable']}")

    out_file = Path('review/2026-10-14/evidence/g7/cvat-task-spec-vn.json')
    combined = {
        'task': task_data,
        'jobs': jobs_data,
        'labels': labels_data
    }
    out_file.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Task details saved to {out_file}.")

if __name__ == '__main__':
    main()
