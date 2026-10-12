from unittest.mock import Mock
import pytest
from pointsnap.core.config import load_config
from pointsnap.core.model import Cuboid,ErrorType,Finding,Severity
from pointsnap.core.synthetic import InjectedError
from pointsnap.eval.evaluate import ErrorOutcome,evaluate_scene,summarize


def test_canonical_size_measurement_uses_relative_difference(monkeypatch):
    boxes = [Cuboid((0, 0, 0), (4, 2, 1.5), 0, 'car', frame, track_id=7) for frame in range(3)]
    reader = Mock()
    reader.frames.return_value.num_frames = 3
    reader.annotations.return_value = boxes
    error = InjectedError('size_in_track', .3, 7, 1, None, 'fixture', (4, 2, 1.5), (5.2, 2.6, 1.95))
    finding = Finding(ErrorType.SIZE, 'size.in_track', Severity.ERROR, 1, 'car', '30%',
                      track_id=7, value=1.2, details={'relative_diff': .3, 'median': 4.0})
    monkeypatch.setattr('pointsnap.eval.evaluate.inject_dataset', lambda *a, **kw: (boxes, [error]))
    monkeypatch.setattr('pointsnap.eval.evaluate.scan_cuboids', Mock(side_effect=[[], [finding]]))
    stats, outcomes = evaluate_scene(reader, 'fixture', load_config(env={}), rounds=1)
    accuracy = summarize([stats], outcomes)['measurement_accuracy']['size_in_track']
    assert accuracy['median_abs_error'] == pytest.approx(0)


def test_old_size_outcomes_without_units_do_not_claim_an_accuracy():
    outcome = ErrorOutcome('fixture', 0, 'size_in_track', '0.3', 7, 1, 'car',
                           True, True, 'error', 1.2, .3, None)
    accuracy = summarize([], [outcome])['measurement_accuracy']['size_in_track']
    assert accuracy['n'] == 0 and accuracy['median_abs_error'] is None


def test_evaluation_archive_cannot_claim_the_parent_checkout_commit(tmp_path, monkeypatch):
    from pointsnap.eval import evaluate
    copied_module = tmp_path / 'archive/pointsnap/eval/evaluate.py'
    copied_module.parent.mkdir(parents=True)
    copied_module.write_text('# archived evaluator fixture\n', encoding='utf-8')
    monkeypatch.setattr(evaluate, '__file__', str(copied_module))
    monkeypatch.setattr(evaluate, 'evaluate_scene', lambda *a, **kw: (evaluate.SceneStats('fixture', 1), []))
    evaluate.run_evaluation(Mock(version='fixture'), ['fixture'], load_config(env={}),
                            tmp_path / 'results', rounds=1, progress=lambda _: None)
    import json
    metadata = json.loads((tmp_path / 'results/metadata.json').read_text(encoding='utf-8'))
    assert metadata['source_commit'] is None
