import argparse
import logging
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import librosa
import torch
import torchaudio
from pydub import AudioSegment
from tqdm import tqdm

from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.common import set_all_random_seed
from cosyvoice.utils.file_utils import load_wav
from utils import read_audio_script_from_xlsx

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append('cosyvoice/third_party/Matcha-TTS'.format(ROOT_DIR))
prompt_sr = 16000
max_val = 0.8


class CVWrapper:
    def __init__(self, model):
        self.model = model
        self.busy = False
        self._lock = Lock()

    def get_model(self):
        with self._lock:
            return self.model

    def is_busy(self):
        with self._lock:
            return self.busy

    def release_model(self):
        with self._lock:
            self.busy = False


class ModelPool:
    def __init__(self, num):
        self.model_pool = []
        for i in range(num):
            self.model_pool.append(CVWrapper(CosyVoice2('cosyvoice/pretrained_models/CosyVoice2-0.5B')))

    def request_free_model(self) -> CVWrapper:
        print('Requesting free model...')
        while True:
            for model in self.model_pool:
                if not model.is_busy():
                    model.busy = True
                    return model


model_pool = None


def dub_an_audio(cosyvoice, prompt_audio_path, target_text, out_audio_path):

    def postprocess(speech, top_db=60, hop_length=220, win_length=440):
        speech, _ = librosa.effects.trim(
            speech, top_db=top_db,
            frame_length=win_length,
            hop_length=hop_length
        )
        if speech.abs().max() > max_val:
            speech = speech / speech.abs().max() * max_val
        speech = torch.concat([speech, torch.zeros(1, int(cosyvoice.sample_rate * 0.2))], dim=1)
        return speech

    if not os.path.exists(prompt_audio_path):
        raise FileNotFoundError('prompt audio not found: {}'.format(prompt_audio_path))
    if os.path.exists(out_audio_path):
        print(f'AI dubbed Audio already exists: {out_audio_path}')
        return

    # 如果prompt_audio音频的采样率低于prompt_sr，则先resample然后覆盖原文件（使用pydub）
    audio = AudioSegment.from_file(prompt_audio_path)
    if audio.frame_rate < prompt_sr:
        print(f'Resampling prompt audio to {prompt_sr}Hz: {prompt_audio_path}')
        audio = audio.set_frame_rate(prompt_sr)
        audio.export(prompt_audio_path, format="wav")

    prompt_speech = postprocess(load_wav(prompt_audio_path, prompt_sr))
    seed = random.randint(1, 100000000)
    set_all_random_seed(seed)

    cut_num = 0
    for i, j in enumerate(cosyvoice.inference_cross_lingual(target_text, prompt_speech, stream=False, speed=1.0)):
        cut_num += 1
        out_audio_path_per = out_audio_path
        if i > 0:
            out_audio_path_per = out_audio_path.replace('.wav', '_{}.wav'.format(i))

        torchaudio.save(out_audio_path_per, j['tts_speech'], cosyvoice.sample_rate)

    if cut_num > 1:  # 如果生成了多个音频，则合并为一个音频
        print(f'Merging audio files...{out_audio_path}')
        audio = AudioSegment.from_file(out_audio_path)  # 读取第0个音频文件作为基底
        for i in range(1, cut_num):  # 合并剩余的音频文件
            audio_per = AudioSegment.from_file(out_audio_path.replace('.wav', '_{}.wav'.format(i)))
            audio = audio.overlay(audio_per)
        audio.export(out_audio_path, format="wav")
        for i in range(1, cut_num):  # 删除带序号的临时音频文件
            os.remove(out_audio_path.replace('.wav', '_{}.wav'.format(i)))

    print(f'Done dubbing {out_audio_path}')


def process_a_audio_group(xlsx_path: str, in_audio_dir: str, out_audio_dir: str, cosyvoice: CosyVoice2 = None):
    if cosyvoice is None:
        cosyvoice = CosyVoice2('cosyvoice/pretrained_models/CosyVoice2-0.5B')

    # 读取音频脚本映射
    audio_cn_script_map = read_audio_script_from_xlsx(xlsx_path, audio_col='音频文件', script_col='AI翻译简中')

    # 遍历音频脚本映射，进行逐个配音
    for audio_name, cn_script in tqdm(audio_cn_script_map.items(), desc="正在配音"):
        cn_script = audio_cn_script_map.get(audio_name)
        audio_filename = audio_name + '.wav'

        prompt_audio_path = os.path.join(in_audio_dir, audio_filename)
        target_text_cn = cn_script
        out_audio_path = os.path.join(out_audio_dir, audio_filename)

        # 调用CosyVoice进行配音
        dub_an_audio(cosyvoice, prompt_audio_path, target_text_cn, out_audio_path)


def process_xlsx(xlsx):
    print(f'Processing xlsx: {xlsx}')
    in_audio_dir = os.path.join(args.in_audio_dirs_root, os.path.basename(xlsx).replace('.xlsx', ''))
    out_audio_dir = os.path.join(args.out_audio_dirs_root, os.path.basename(xlsx).replace('.xlsx', ''))
    if not os.path.exists(in_audio_dir):
        os.makedirs(in_audio_dir)
    if not os.path.exists(out_audio_dir):
        os.makedirs(out_audio_dir)

    cvw: CVWrapper = model_pool.request_free_model()
    process_a_audio_group(xlsx, in_audio_dir, out_audio_dir, cvw.get_model())
    cvw.release_model()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='SFX AI Dub using CosyVoice2, need xlsx generated by sensevoice from ori sfx. 使用跨域种模式还原音色')

    parser.add_argument('--in-audio-dirs-root', type=str,
                        default='./in_audio/S_FULL_AMB_M.rpf',
                        help='root directory of ori audio directories')
    parser.add_argument('--out-audio-dirs-root', type=str,
                        default='./out_sfx/S_FULL_AMB_M.rpf',
                        help='root directory of audio directories')
    parser.add_argument('--xlsx-root-dir', type=str,
                        default='./in_xlsx/S_FULL_AMB_M.rpf',
                        help='root directory of xlsx files')
    parser.add_argument('--xlsx', type=str, nargs='+',
                        default=[],
                        help='xlsx(s) to be dubbed')

    parser.add_argument('--ncpu', type=int, default=7,
                        help='number of cpu to use')

    args = parser.parse_args()

    if args.xlsx is None or len(args.xlsx) == 0:
        args.xlsx = [os.path.join(args.xlsx_root_dir, f) for f in os.listdir(args.xlsx_root_dir) if f.endswith('.xlsx')]


    model_pool = ModelPool(args.ncpu)
    print(f'Using {args.ncpu} models for dubbing.')
    with ThreadPoolExecutor(max_workers=args.ncpu) as executor:
        executor.map(process_xlsx, args.xlsx)
