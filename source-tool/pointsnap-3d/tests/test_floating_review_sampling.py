"""Sampling must not favour correctable findings or count the same track repeatedly."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

spec = spec_from_file_location('floating_review', Path(__file__).parents[1] / 'scripts/prepare_floating_review.py')
module = module_from_spec(spec)
spec.loader.exec_module(module)


def item(scene, track, frame, eligible=False):
    return {'scene': scene, 'finding': SimpleNamespace(track_id=track, frame=frame, label='car'),
            'preview_eligible': eligible}


def test_scene_round_robin_uses_distinct_tracks_and_does_not_favour_preview_eligibility():
    rows = [item('b', 3, 0, True), item('a', 1, 9, True), item('a', 2, 1, True),
            item('a', 1, 0, False), item('b', 4, 1, False)]
    selected = module.select_cases(rows, 4)
    assert [(r['scene'], r['finding'].track_id, r['finding'].frame) for r in selected] == [
        ('a', 1, 0), ('b', 3, 0), ('a', 2, 1), ('b', 4, 1)]
    assert not selected[0]['preview_eligible']


def test_selection_is_deterministic_across_candidate_input_order_and_can_be_smaller_than_requested():
    rows = [item('b', 2, 1), item('a', 1, 3), item('a', 1, 0)]
    assert module.select_cases(rows, 20) == module.select_cases(list(reversed(rows)), 20)
    assert len(module.select_cases(rows, 20)) == 2


def test_packet_identity_changes_with_measurement_config_or_image_evidence():
    before=module.packet_id('cfg',[{'value':.2}],{'camera.jpg':'image-a'})
    assert before != module.packet_id('cfg',[{'value':.3}],{'camera.jpg':'image-a'})
    assert before != module.packet_id('new-cfg',[{'value':.2}],{'camera.jpg':'image-a'})
    assert before != module.packet_id('cfg',[{'value':.2}],{'camera.jpg':'image-b'})


def test_csv_has_evidence_identity_and_never_seeds_an_attached_verdict(tmp_path):
    import csv
    finding={'frame':1,'track_id':7,'label':'car','rule':'floating','severity':'warning',
             'message':'quote "and"\nnewline','verdict':'Đúng lỗi','repair_verdict':'Tốt hơn'}
    provenance={'packet_id':'test-packet','source_commit':'test-source','config_sha256':'test-config'}
    path=tmp_path/'template.csv'
    module.write_verdict_template(path,[{'scene':'synthetic','finding':finding}],provenance)
    rows=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
    assert len(rows)==1 and rows[0]['message']==finding['message']
    assert rows[0]['verdict']=='' and rows[0]['repair_verdict']==''
    assert all(rows[0][key]==value for key,value in provenance.items())
