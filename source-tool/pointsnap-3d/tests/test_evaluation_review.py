from dataclasses import replace
import json
import pytest

from pointsnap.core.config import load_config
from pointsnap.core.model import ErrorType, Finding, Severity
from pointsnap.core.synthetic import inject_dataset, InjectedError
from pointsnap.eval.evaluate import summarize, run_evaluation, is_applicable, SceneStats
from pointsnap.eval.metrics import evaluate_findings, InjectedFault, MetricSummary, EvaluationReport
from pointsnap.adapters.nuscenes import NuScenesReader
from tests.fake_nuscenes import build


def finding(severity=Severity.ERROR, rule='floating'):
    return Finding(ErrorType.FLOATING, rule, severity, 1, 'car', 'test', track_id=7)


def test_info_is_not_a_true_positive():
    report=evaluate_findings([InjectedFault('floating',1,7)], [finding(Severity.INFO)])
    assert (report.overall.true_positives,report.overall.false_negatives)==(0,1)


def test_matching_respects_explicit_rule():
    report=evaluate_findings([InjectedFault('floating',1,7,rule='floating')], [finding(rule='floating.no_evidence')])
    assert report.overall.true_positives==0 and report.overall.false_positives==1


def test_unknown_denominators_do_not_report_zero_or_pass():
    report=EvaluationReport()
    assert MetricSummary().precision is None and MetricSummary().recall is None
    assert report.false_alarm_rate_per_100 is None
    assert 'CHƯA ĐO' in report.to_markdown()
    assert '**0.00** Cảnh báo' not in report.to_markdown()


def test_clean_error_and_warning_have_separate_denominators():
    report=evaluate_findings([],[],200,[finding(),finding(Severity.WARNING)])
    assert report.clean_warning_count==1 and report.clean_error_count==1
    assert report.clean_false_alarms==2
    assert '0.50' in report.to_markdown()


def test_empty_canonical_summary_is_defined():
    assert summarize([SceneStats('empty',0,clean={'floating|warning':1})],[])['clean_per_100_boxes']['floating|warning'] is None


def test_zero_error_rate_injects_nothing(tmp_path):
    boxes=NuScenesReader(build(tmp_path/'dataset')).annotations('scene-0001')
    assert inject_dataset(boxes,error_rate=0)[1]==[]


@pytest.mark.parametrize('rate',[-.1,1.1,float('nan')],ids=['negative','above-one','nan'])
def test_invalid_injection_rate_rejected(rate):
    with pytest.raises(ValueError): inject_dataset([],error_rate=rate)


def test_disabled_rule_excludes_injection_from_applicable_scope():
    cfg=load_config(env={});cfg=replace(cfg,rules=replace(cfg.rules,floating=False))
    error=InjectedError('floating',.4,7,1,None,'test',0,.4)
    assert not is_applicable(error,'car',[],cfg,None)


def test_eval_records_reproducibility_metadata(tmp_path):
    reader=NuScenesReader(build(tmp_path/'dataset'))
    out=tmp_path/'result'
    run_evaluation(reader,['scene-0001'],load_config(env={}),out,rounds=1,seed=7,progress=lambda _:None)
    data=json.loads((out/'metadata.json').read_text())
    assert data['rounds']==1 and data['seed']==7 and data['catalog']=='all'
    assert len(data['config_sha256'])==64 and data['dataset_version']=='v1.0-mini'
    assert (out/'injections.json').is_file()


@pytest.mark.parametrize('scenes,rounds', [([],1),(['scene-0001'],0),(['scene-0001'], -1),(['scene-0001','scene-0001'],1)])
def test_invalid_evaluation_input_rejected_before_scanning(tmp_path,scenes,rounds):
    with pytest.raises(ValueError):
        run_evaluation(None,scenes,load_config(env={}),tmp_path/'out',rounds=rounds)


def test_a_finding_is_not_credited_to_two_injections():
    report=evaluate_findings([InjectedFault('floating',1,7),InjectedFault('floating',1,7)],[finding()])
    assert (report.overall.true_positives,report.overall.false_negatives)==(1,1)


def test_size_measurement_needs_explicit_expected_quantity():
    f=Finding(ErrorType.SIZE,'size.class_range',Severity.ERROR,1,'car','length',track_id=7,value=8)
    report=evaluate_findings([InjectedFault('size',1,7,delta=3)],[f])
    assert report.by_type['size'].measurement_errors==[]


def test_seed_repeat_is_identical_and_split_is_disjoint(tmp_path):
    from pointsnap.eval.split import TUNING_SCENES, TEST_SCENES
    boxes=NuScenesReader(build(tmp_path/'dataset')).annotations('scene-0001')
    assert inject_dataset(boxes,seed=17)==inject_dataset(boxes,seed=17)
    assert len(set(TUNING_SCENES)|set(TEST_SCENES))==10 and not set(TUNING_SCENES)&set(TEST_SCENES)
