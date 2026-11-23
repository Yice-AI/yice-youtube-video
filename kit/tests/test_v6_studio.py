import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KIT), str(KIT/'scripts')]
from audit_v6 import rectangles, timeline_gates
from editorial import EditorialStage
from studio_ui import add_workbench
from voice import resolve_backend


def test_cloud_stages():
    with patch.dict('os.environ',{'KAGGLE_TTS_ENDPOINT_URL':'https://draft','MODAL_QWEN3_TTS_ENDPOINT_URL':'https://master'},clear=True):
        assert resolve_backend('draft','auto')=='kaggle'
        assert resolve_backend('master','auto')=='modal'
    with patch.dict('os.environ',{},clear=True), pytest.raises(ValueError):
        resolve_backend('master','auto')
    with pytest.raises(ValueError):resolve_backend('draft','local')
    assert resolve_backend('draft','local',True)=='local'


def test_mask_in_textured_viewport():
    frame=np.random.default_rng(4).integers(18,195,(270,480,3),dtype=np.uint8)
    frame[40:150,120:245]=235
    assert len(rectangles(frame))==1
    assert not rectangles(np.full_like(frame,235))


def test_lock_uses_caption_source(tmp_path):
    data={'shots':[dict(start=1,end=4,id='s',kind='studio_ui',files=['codex-live.mp4'],anchor_cue_id='q',anchor_cue_start=1,outer_scale=1.2)],
          'captions':[dict(id='q',firstCharTime=1.55)]}
    errors=[]
    metrics=timeline_gates(data,tmp_path,4,errors)
    assert metrics['banned_sources']
    assert metrics['av_sync_lock_gate']['violations']==['s']
    assert metrics['viewport_safe_margin_gate']['violations']==['s']


@pytest.mark.parametrize('style', ['nle_timeline','audio_daw','vscode_workbench','terminal_pipeline'])
def test_workbench_uses_evidence(style):
    stage=EditorialStage('测试')
    data=dict(monitor='assets/monitor.mp4', media=['monitor.mp4'],tracks=[[(0,.4)],[(.4,.6)],[(.6,1)]],
              voice=[.1,.6],bed=[.2,.3],drops=[(.2,.23)],meter='−13.9 LUFS',file='shots.json',
              tree=['shots.json'],lines=['+ 真实证据'],command='ffprobe',status='已读取',evidence=['assets/record.json'])
    add_workbench(stage,0,6,style,'核对实际数据',data)
    assert stage.shots[-1]['kind']=='studio_ui'
    assert stage.shots[-1]['files']
    assert stage.scripts and '核对实际数据' in stage.plates[-1]
