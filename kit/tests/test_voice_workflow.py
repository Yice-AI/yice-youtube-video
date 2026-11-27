"""Synthetic audio only; no model generation, network or private recordings."""
import hashlib
import importlib.util
import os
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
import soundfile as sf

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import voice
quality = voice.load_voice_tool('voice-quality')
post = voice.load_voice_tool('voice-post')
repair = voice.load_voice_tool('voice-repair')


def synthetic(path, text, durations=None, frequency=160):
    rate, samples, rows, words = 24000, [np.zeros(2400)], [], []
    cursor, count = .1, 0
    for index, char in enumerate(text):
        if not char.isalnum():
            if char in '。！？':
                samples.append(np.zeros(7200)); cursor += .3
            continue
        duration = durations[count] if durations else .16
        size = round(duration*rate)
        time = np.arange(size)/rate
        y = .1*np.sin(2*np.pi*frequency*time)
        fade = min(120, size//2)
        y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
        samples.append(y)
        rows.append(dict(charStart=index, charEnd=index+1, s=cursor, e=cursor+size/rate))
        words.append(dict(word=char, start=cursor, end=cursor+size/rate))
        cursor += size/rate; count += 1
    samples.append(np.zeros(2400))
    sf.write(path, np.concatenate(samples), rate, subtype='PCM_24')
    return dict(text=text, mapped=rows), dict(text=text, segments=[dict(text=text, words=words)])


class VoiceWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_seed_validation_and_every_chapter_seed_is_generated(self):
        self.assertEqual(quality.seeds('42,43'), [42, 43])
        for value in ['42,42', '', '-1', '4294967296', '42,x']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                quality.seeds(value)
        backend = mock.Mock()
        backend.clone = dict(audio='synthetic', text='reference', language='zh')
        def generate(**kwargs):
            Path(kwargs['output_path'], kwargs['file_prefix']+'.wav').write_bytes(b'SYNTHETIC'*10)
        backend.generate.side_effect = generate
        with mock.patch.dict(sys.modules, {'local_voiceover': types.SimpleNamespace(
                MLXBackend=lambda *_: backend, load_clone=lambda _: backend.clone)}):
            voice.generate_raw([dict(id='00', text='甲'), dict(id='01', text='乙')], self.root, 'test', [42,43])
        self.assertEqual([call.args[0] for call in backend.mx.random.seed.call_args_list], [42,43,42,43])
        self.assertEqual(len(list(self.root.rglob('*.wav'))), 4)

    def test_candidate_selection_requires_asr_and_zero_alerts(self):
        def candidate(seed, ok, ratio, alerts):
            return dict(seed=seed, asr=dict(ok=ok, ratio=ratio, differences=[] if ok else [1]), check=dict(alerts=[1]*alerts))
        choices = [candidate(42, True, 1., 2), candidate(43, False, .99, 0), candidate(44, True, .98, 0)]
        self.assertEqual(min(choices, key=quality.rank)['seed'], 44)

    def test_number_unit_english_and_homophone_exceptions_are_separate(self):
        expected = '三十张一百三十二兆十五兆，Codex检查张数。'
        result = quality.audit(expected, {'text': '30张132Mbps15照，Code X检查章数。'},
                               {'homophone': {'张数': '章数'}})
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['ratio'], 1.)
        self.assertTrue(result['number_unit']); self.assertTrue(result['english_name']); self.assertTrue(result['homophone'])
        self.assertIn('Mbps', json.dumps(result['number_unit']))
        self.assertEqual(expected, '三十张一百三十二兆十五兆，Codex检查张数。')

    def test_mixed_language_speed_counts_pronunciation_units(self):
        vc = voice.load_voice_tool('voice-check')
        wav = self.root / 'mixed.wav'
        durations = [0.18] * 6 + [0.098] * 11
        aligned, _ = synthetic(wav, '甲乙丙丁戊己。摄影师是Harness。', durations=durations)
        result = vc.check_chapter(wav, aligned)
        self.assertEqual([a for a in result['alerts'] if a['kind'] == 'duration_or_rate_outlier'], [])

    def test_wrong_number_and_unregistered_chinese_typo_never_pass(self):
        for expected, heard, rules in [('三十兆', '31Mbps', {}), ('十五', '五十', {'十五':'五十'}),
                                       ('十五兆', '五十兆', {'number_unit': {'十五兆':'五十兆'}}),
                                       ('检查张数', '检查章数', {}), ('甲'*100+'乙', '甲'*100+'丙', {})]:
            with self.subTest(heard=heard):
                result = quality.audit(expected, {'text': heard}, rules)
                self.assertFalse(result['ok'])
                self.assertTrue(result['differences'])
        self.assertFalse(quality.audit('甲'*100, {'text':'甲'*90})['ok'])

    def test_three_does_not_corrupt_thirty_in_timing_normalization(self):
        transcript = {'segments':[{'words':[{'word':'30和3','start':0,'end':3}]}]}
        mapped, ratio, _ = voice.align_characters('三十和三', transcript, 3, {'三':'3', '三十':'30'})
        self.assertEqual(ratio, 1.)
        self.assertEqual([row['charStart'] for row in mapped], [0,1,2,3])
        self.assertTrue(all(a['e'] <= b['s'] for a,b in zip(mapped,mapped[1:])))

    def test_lufs_preserves_samples_and_post_runs_detection_after_normalizing(self):
        source, target = self.root/'source.wav', self.root/'post.wav'
        aligned, _ = synthetic(source, '甲乙丙丁戊己庚辛。')
        original = source.read_bytes()
        with mock.patch.object(post.pd, 'check_chapter', wraps=post.pd.check_chapter) as check:
            result = post.postprocess(source, aligned, target, speed=1)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(sf.info(source).frames, sf.info(target).frames)
        self.assertAlmostEqual(result['postprocessing']['loudness']['measured_lufs'], -16, delta=.5)
        self.assertLessEqual(result['postprocessing']['loudness']['true_peak_dbtp'], -1)
        check.assert_called_once()
        self.assertEqual(check.call_args.args[0], target)
        self.assertIn('post_check', result)

    def test_low_alignment_ratio_is_a_failed_chapter_even_when_prosody_passes(self):
        source = self.root/'raw.wav'
        aligned, transcript = synthetic(source, '甲乙丙丁。')
        chapter = dict(id='00',text=aligned['text'],scenes=[dict(id='0-1',text=aligned['text'])])
        (self.root/'analysis').mkdir()
        with mock.patch.object(voice,'align_characters',return_value=(aligned['mapped'],.90,0)):
            result = voice.finish_chapter(chapter, source, self.root, transcript, {}, 0, 0, [], skip_post=True)
        self.assertFalse(result[-1]['ok'])
        self.assertFalse(result[-1]['asr']['ok'])
        self.assertTrue(result[-1]['prosody_ok'])

    def test_continuity_rejects_octave_shift_and_accepts_same_voice(self):
        rate = 24000
        t = np.arange(rate)/rate
        before = .1*np.sin(2*np.pi*160*t)
        self.assertTrue(repair.continuity(before, before*.9, rate)['ok'])
        bad = repair.continuity(before,.1*np.sin(2*np.pi*320*t),rate)
        self.assertFalse(bad['ok'])
        self.assertGreater(abs(bad['pitch_shift_semitones']),3.5)

    def test_sentence_cut_refuses_a_boundary_without_natural_quiet(self):
        source = self.root/'raw.wav'
        aligned, _ = synthetic(source, '甲乙。 丙丁。')
        with mock.patch.object(repair.check_tool,'measure',return_value={'relative_quiet':[]}):
            with self.assertRaisesRegex(ValueError,'自然低能量'):
                repair.cuts_for(source,aligned)

    def test_successful_sentence_repair_keeps_original_and_outputs_clips_and_full_scan(self):
        source = self.root/'original.wav'
        text='甲乙丙。 丁戊己庚。'
        aligned, _ = synthetic(source,text,[.16,.16,.16,.16,.16,.52,.16])
        original=source.read_bytes()
        audit=quality.audit(text,{'text':text})
        check=repair.check_tool.check_chapter(source,aligned)
        self.assertFalse(check['ok'])
        current=dict(audio=str(source),alignment=aligned,asr=audit,check=check,seed=42)
        transcripts={}
        def generate(jobs):
            for job in jobs:
                _, transcript=synthetic(job['path'],job['text'])
                transcripts[str(job['path'])]=transcript
        def transcribe(path):
            return transcripts.get(str(path),{'text':text})
        chapter=dict(id='00',text=text,scenes=[dict(id='0-1',text=text)])
        result=repair.repair(chapter,current,self.root/'repair',generate,transcribe,post_options={'speed':1})
        self.assertTrue(result['check']['ok'],result['check']['alerts'])
        self.assertTrue(result['asr']['ok'])
        self.assertEqual(source.read_bytes(),original)
        self.assertTrue(list((self.root/'repair').rglob('*-before.wav')))
        self.assertTrue(list((self.root/'repair').rglob('*-after.wav')))
        self.assertEqual(result['alignment']['text'],text)
        self.assertTrue(all(splice['fade_ms']==15 for row in result['repair_rounds'] for splice in row['splices']))

    def test_no_acceptable_candidate_stops_after_three_rounds(self):
        source=self.root/'source.wav'
        text='甲乙。'
        aligned, transcript=synthetic(source,text)
        current=dict(audio=str(source),alignment=aligned,asr=quality.audit(text,{'text':text}),
                     check={'ok':False,'alerts':[{'sentence':0}]},seed=42)
        calls=[]
        def generate(jobs):
            calls.append(jobs)
            for job in jobs: shutil.copy2(source,job['path'])
        with mock.patch.object(repair,'continuity',return_value={'ok':False,'mfcc_mean_cosine':.5,'pitch_shift_semitones':8}):
            result=repair.repair(dict(id='00',text=text,scenes=[dict(id='0-1',text=text)]),current,
                                 self.root/'repair',generate,lambda _:transcript,post_options={'speed':1})
        self.assertFalse(result['check']['ok'])
        self.assertEqual(len(calls),3)
        self.assertEqual(len({job['seed'] for jobs in calls for job in jobs}),9)
        self.assertEqual(result['audio'],str(source))

    def test_cache_requires_exact_text_seed_brand_and_audio_hash(self):
        source=self.root/'source.wav'
        synthetic(source,'甲乙。')
        cache=self.root/'cache.json'
        item=dict(text='甲乙。',seed=42,brand='test',path=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        cache.write_text(json.dumps([item]))
        generate=voice.make_generator('test',self.root/'jobs',cache)
        generate([dict(text='甲乙。',seed=42,path=str(self.root/'copy.wav'))])
        self.assertEqual((self.root/'copy.wav').read_bytes(),source.read_bytes())
        source.write_bytes(source.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'哈希'):
            generate([dict(text='甲乙。',seed=42,path=str(self.root/'bad.wav'))])

    def test_cloud_whisper_long_audio_keeps_absolute_words_and_caches_result(self):
        import base64
        import io
        import numpy as np
        import soundfile as sf

        sound = self.root / 'long.wav'
        sf.write(sound, np.linspace(0., .04, 45 * 16000), 16000)
        durations = []
        def recognize(request, timeout):
            self.assertTrue(request.full_url.endswith('/asr'))
            self.assertEqual(request.get_header('Authorization'), 'Bearer fixture')
            wav = base64.b64decode(json.loads(request.data)['audio'])
            durations.append(sf.info(io.BytesIO(wav)).duration)
            return io.BytesIO(json.dumps(dict(text='甲', segments=[dict(start=0, end=.5,
                                              words=[dict(word='甲', start=0, end=.5)])])).encode())
        env = dict(KAGGLE_TTS_ENDPOINT_URL='https://example.invalid/tts', KAGGLE_TTS_TOKEN='fixture')
        with mock.patch.dict(os.environ, env), mock.patch('urllib.request.urlopen', side_effect=recognize):
            transcribe = voice.kaggle_transcriber(self.root / 'cloud-asr')
            result = transcribe(sound)
            self.assertEqual(transcribe(sound), result)
        self.assertGreater(len(durations), 1)
        self.assertLessEqual(max(durations), 25)
        self.assertAlmostEqual(sum(durations), 45)
        for index, segment in enumerate(result['segments']):
            self.assertAlmostEqual(segment['words'][0]['start'], sum(durations[:index]))

    def test_reviewed_raw_pcm_is_checked_again_if_postprocessing_changes_transcript(self):
        folder=self.root/'selection'
        folder.mkdir()
        chapter=dict(id='01', text='甲乙。')
        raw_folder=folder/'seed42'
        (raw_folder/'analysis').mkdir(parents=True)
        (raw_folder/'analysis/raw-transcript.json').write_text(json.dumps({'text':'甲乙。'}))
        def result(ok):
            return dict(seed=42, folder=str(raw_folder), alignment={'text':'甲乙。'}, check=dict(ok=ok, alerts=[]),
                        asr=quality.audit('甲乙。', {'text':'甲乙。' if ok else '甲甲。'}),
                        record=dict(generated_duration=1.,added_boundary_silence=0.))
        with mock.patch.object(repair,'screen_chapter',side_effect=[result(False),result(True)]) as screen:
            chosen=repair.process_chapter(chapter,[dict(seed=42,path='reviewed.wav',reused_sha256='verified')],
                folder,None,None,profile='natural_v7',cloud_backend='kaggle',post_options={'speed':1.})
        self.assertTrue(chosen['check']['ok'])
        self.assertEqual(chosen['record']['mastering_source'], 'verified_original_pcm')
        self.assertIs(screen.call_args.args[9], True)

    def test_asr_cache_is_tied_to_audio_hash_and_settings(self):
        source=self.root/'source.wav'; source.write_bytes(b'first')
        mocked=mock.Mock(return_value={'text':'甲'})
        with mock.patch.dict(sys.modules,{'mlx_whisper':types.SimpleNamespace(transcribe=mocked)}):
            transcribe=voice.make_transcriber('model','terms',self.root/'asr')
            transcribe(source); transcribe(source)
            source.write_bytes(b'second'); transcribe(source)
            voice.make_transcriber('model','new terms',self.root/'asr')(source)
        self.assertEqual(mocked.call_count,3)

    def test_semantic_chunks_preserves_every_character_when_tail_merges(self):
        text = (
            "我的视频，是一个AI团队做的。经理Claude，员工Codex，摄影Harness。"
            "我在里面，只干一件事：说“不行”。前两期出来，就是这样。一张卡片飞进来，停住。"
            "下一张飞进来，再停住。像一份会自己翻页的PPT。我当时的原话是：“除了录屏、AI生成的图，就没有其他素材了。"
            "每个视频都这样，那就很单调了。”问题出在哪？我的第一反应，跟你现在想的，大概一样。"
        )
        chunks = voice.semantic_chunks(text)
        self.assertEqual("".join(chunks), text)
        self.assertTrue(chunks[0].startswith("我的视频"))
        self.assertTrue(chunks[-1].endswith("大概一样。"))

    def test_local_backend_chunks_long_paragraphs_and_applies_pronunciation_notes(self):
        script = self.root / 'script.md'
        s1 = '第一个出场的是归藏〔读：归葬〕开源的网页演示工具，把六行提纲丢给助手就能直接吐出单文件网页。'
        s2 = '打开浏览器按方向键横向翻页，克莱因蓝点阵底纹配上超大号数字看板，完全没有密密麻麻的字墙感。'
        s3 = '同一份提纲换一句指令切到电子杂志风格，背景立刻变成实时流动的暖色光影，断网双击也能全屏路演。'
        script.write_text(f'## 01 演示\n| 幕 | 旁白 |\n| --- | --- |\n| 1-1 | {s1} |\n| 1-2 | {s2} |\n| 1-3 | {s3} |\n')
        chapters = voice.parse_script(script)
        self.assertIn('归藏开源', chapters[0]['text'])
        self.assertNotIn('归葬', chapters[0]['text'])
        self.assertEqual(chapters[0]['pronunciations'], {'归藏': '归葬'})

        calls = []
        backend = mock.Mock()
        backend.clone = dict(audio='synthetic', text='reference', language='zh')
        def generate(**kwargs):
            calls.append(kwargs['text'])
            target = Path(kwargs['output_path'], kwargs['file_prefix'] + '.wav')
            synthetic(target, kwargs['text'])
        backend.generate.side_effect = generate
        with mock.patch.dict(sys.modules, {'local_voiceover': types.SimpleNamespace(
                MLXBackend=lambda *_: backend, load_clone=lambda _: backend.clone)}):
            voice.generate_raw(chapters, self.root / 'out', 'test', [42], backend='local', chunk_mode='long_paragraph')
        self.assertGreaterEqual(len(calls), 2)
        self.assertTrue(any('归葬开源' in c for c in calls))
        self.assertFalse(any('归藏' in c for c in calls))
        wav = self.root / 'out/seed42/chapter-01-raw.wav'
        self.assertTrue(wav.is_file() and sf.info(wav).frames > 24000)
        self.assertTrue((wav.with_suffix('.chunks') / 'chunks.json').is_file())

    def test_aspect_ratio_and_extended_single_reading_homophones(self):
        result = quality.audit('小红书三比四竖版套图，杂志风与现成组件。',
                               {'text': '小红书3-4竖板套图，杂志封与线程组件。'},
                               auto_homophone=True)
        self.assertTrue(result['ok'], result)
        self.assertFalse(quality.audit('小红书三比四竖版', {'text': '小红书3-5竖版'}, auto_homophone=True)['ok'])


if __name__=='__main__':
    unittest.main()
