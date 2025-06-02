import argparse
import os
import random
import sys

from tqdm import tqdm

from utils import read_audio_script_from_xlsx

sys.path.append('cosyvoice/third_party/Matcha-TTS')
from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from cosyvoice.utils.common import set_all_random_seed
import torchaudio
import torch


class CosyVoiceWrapper:
    def __init__(self, model_path):
        if 'CosyVoice2' in os.path.basename(model_path):
            self.cosyvoice = CosyVoice2(model_path)
        else:
            self.cosyvoice = CosyVoice(model_path)

        print(self.cosyvoice.list_available_spks())

    def tts_item_by_pretrained_spk(self, audio_save_path, text, spk_id='云杰', speed=1.0):
        set_all_random_seed(random.randint(1, 100000000))
        audio_tensor_concat = None
        for i in self.cosyvoice.inference_sft(text, spk_id, speed=speed):
            audio_tensor = i['tts_speech']
            if audio_tensor_concat is None:
                audio_tensor_concat = audio_tensor
            else:
                print('Concatenating audio tensors...')
                audio_tensor_concat = torch.cat([audio_tensor_concat, audio_tensor])
        if audio_tensor_concat is None:
            print('No audio generated for text: {}'.format(text))
            return
        torchaudio.save(audio_save_path, audio_tensor_concat, self.cosyvoice.sample_rate)

    def tts_batch(self, audio_script_kv, audio_ori_root, audio_save_root, use_pretrain=True, speed=1.0):
        for audio_name, text in audio_script_kv.items():
            audio_ori_path = os.path.join(audio_ori_root, f'{audio_name}.wav')
            audio_save_path = os.path.join(audio_save_root, f'{audio_name}.wav')
            if use_pretrain:
                self.tts_item_by_pretrained_spk(audio_save_path, text, speed=speed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--xlsx', type=str, default=[
        's_m_y_swat_01_white_full_03.xlsx',
        's_m_y_swat_01_white_full_04.xlsx',
        'spot_suspect_cop_01.xlsx',
        'spot_suspect_cop_02.xlsx',
        'spot_suspect_cop_03.xlsx',
        'spot_suspect_cop_04.xlsx',
        'spot_suspect_cop_05.xlsx',
    ], help='要AI配音的台词表')

    parser.add_argument('--xlsx-root', default='in_xlsx', type=str, help='要批量AI配音的台词表所在文件夹')
    parser.add_argument('--audio-ori-root', type=str, default='POLICE_SCANNER.rpf/',
                        help='批量AI配音的原始音频所在文件夹的根目录')
    args = parser.parse_args()

    xlsx_list = []
    if args.xlsx.__len__() == 0 and args.xlsx_root is not None:
        xlsx_list = [os.path.join(args.xlsx_root, x) for x in os.listdir(args.xlsx_root) if x.endswith('.xlsx')]
    else:
        xlsx_list = [os.path.join(args.xlsx_root, x) for x in args.xlsx]

    args.audio_ori_root = os.path.join('in_audio', args.audio_ori_root)

    cv = CosyVoiceWrapper('cosyvoice/pretrained_models/CosyVoice-300M')

    for xlsx in tqdm(xlsx_list, total=len(xlsx_list)):
        print(f'Processing {xlsx}...')
        awc_name = os.path.splitext(os.path.basename(xlsx))[0]
        audio_save_root = os.path.join('out_sfx', awc_name)
        os.makedirs(audio_save_root, exist_ok=True)

        audio_script_kv = read_audio_script_from_xlsx(xlsx, audio_col='音频文件', script_col='AI翻译简中')

        cv.tts_batch(audio_script_kv, os.path.join(args.audio_ori_root, awc_name), audio_save_root, use_pretrain=True,
                     speed=1.2)
