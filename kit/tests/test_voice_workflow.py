"""Synthetic audio only; no model generation, network or private recordings."""
import hashlib
import importlib.util
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
        self.assertTrue(all(splice['fade_ms']==10 for row in result['repair_rounds'] for splice in row['splices']))

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

    def test_asr_cache_is_tied_to_audio_hash_and_settings(self):
        source=self.root/'source.wav'; source.write_bytes(b'first')
        mocked=mock.Mock(return_value={'text':'甲'})
        with mock.patch.dict(sys.modules,{'mlx_whisper':types.SimpleNamespace(transcribe=mocked)}):
            transcribe=voice.make_transcriber('model','terms',self.root/'asr')
            transcribe(source); transcribe(source)
            source.write_bytes(b'second'); transcribe(source)
            voice.make_transcriber('model','new terms',self.root/'asr')(source)
        self.assertEqual(mocked.call_count,3)


if __name__=='__main__':
    unittest.main()
