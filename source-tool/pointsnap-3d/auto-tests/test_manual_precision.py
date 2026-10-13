import csv
import pytest
from manual_precision import summarize


def write(path, verdicts):
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['scene','frame','track_id','label','rule','verdict'])
        for frame, verdict in verdicts:
            writer.writerow(['scene',frame,0,'car','floating',verdict])


def test_unknowns_are_excluded_and_rescans_do_not_inflate_independent_tracks(tmp_path):
    path = tmp_path/'reviews.csv'
    write(path, [(0,'Đúng lỗi'),(0,'Đúng lỗi'),(1,'Báo nhầm'),(2,'Không rõ'),(3,'')])
    result = summarize(path)
    assert result['rules']['floating']['precision'] == 0.5
    assert result['rules']['floating']['decided_findings'] == 2
    assert result['rules']['floating']['decided_tracks'] == 1
    assert result['g7_status'] == 'UNASSESSED'


def test_no_decided_samples_is_na(tmp_path):
    path = tmp_path/'reviews.csv'
    write(path, [(0,'Không rõ')])
    assert summarize(path)['rules']['floating']['precision'] is None


@pytest.mark.parametrize('verdicts', [[(0,'Đúng lỗi'),(0,'Báo nhầm')],[(0,'made-up')]])
def test_conflicting_or_unknown_verdicts_are_rejected(tmp_path, verdicts):
    path = tmp_path/'reviews.csv'
    write(path, verdicts)
    with pytest.raises(ValueError):
        summarize(path)
