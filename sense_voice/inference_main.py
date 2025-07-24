#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/FunAudioLLM/SenseVoice). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)
import argparse
import os
import re

from funasr import AutoModel

from utils import natural_sort_key

emo_dict = {
    "|HAPPY|": "HAPPY/高兴",
    "|SAD|": "SAD/沮丧",
    "|ANGRY|": "ANGRY/生气",
    "|NEUTRAL|": "NEUTRAL/中性",
    "|FEARFUL|": "FEARFUL/恐惧",
    "|DISGUSTED|": "DISGUSTED/厌恶",
    "|SURPRISED|": "SURPRISED/惊讶",
    "|EMO_UNKNOWN|": "EMO_UNKNOWN/未知",
}

event_dict = {
    "|BGM|": "BGM/背景音乐",
    "|Speech|": "Speech/说话",
    "|Applause|": "Applause/掌声",
    "|Laughter|": "Laughter/笑声",
    "|Cry|": "Cry/哭声",
    "|Sneeze|": "Sneeze/打哈欠",
    "|Breath|": "Breathe/呼吸",
    "|Cough|": "Cough/咳嗽",
    "|EVENT_UNKNOWN|": "EVENT_UNKNOWN/未知",
}


def construct_sentence_from_str(file, raw_str):
    pattern = r'<([^>]+)><([^>]+)><([^>]+)><([^>]+)>(.*)'
    match = re.match(pattern, raw_str)
    if match:
        emo = match.group(2)
        event = match.group(3)
        text = match.group(5).strip()
        file = file
        return Sentence(file, emo, event, text)
    else:
        raise ValueError("Invalid sentence format.")


class Sentence:

    def __init__(self, file, emo, event, text):
        self.file = file
        self.emo = emo
        self.event = event
        self.text = text

    def get_file(self):
        return self.file

    def get_emo(self):
        return emo_dict.get(self.emo)

    def get_event(self):
        return event_dict.get(self.event)

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.text = text

    def __str__(self):
        return f"文件名：{self.get_file()}，推测情感：{self.get_emo()}，推测事件：{self.get_event()}，文本识别结果：{self.get_text()}"


def get_audio_list(path):
    # 获取path目录下所有wav文件
    import os
    audio_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.wav'):
                audio_list.append(os.path.join(root, file))
    audio_list.sort(key=natural_sort_key)
    print(f"Find {len(audio_list)} audio files in {path}.")
    return audio_list


# from .model import SenseVoiceSmall
# model_dir = "sense_voice/ckpt"
# m, kwargs = SenseVoiceSmall.from_pretrained(model=model_dir, device="cuda:0")
# m.eval()

def infer_main(model, audio_list, batch_size=64):
    batch_res = model.generate(
        input=audio_list,
        cache={},
        language="en",  # "zh", "en", "yue", "ja", "ko", "nospeech"
        use_itn=True,
        batch_size=batch_size,
        batch_size_s=60
    )
    # batch_res = m.inference(
    #     data_in=audio_list,
    #     language="en",  # "zh", "en", "yue", "ja", "ko", "nospeech"
    #     use_itn=True,
    #     ban_emo_unk=True,
    #     **kwargs,
    # )

    return [construct_sentence_from_str(res['key'], res['text']) for res in batch_res]


def rec_sentences(model, audio_dir, batch_size=1):

    audio_list = get_audio_list(audio_dir)

    sentences = infer_main(model, audio_list, batch_size)

    # sentences = []
    # for audio_file in audio_list:
    #     sentences.append(Sentence(os.path.basename(audio_file).split('.')[0], "", "", ""))

    return sentences


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio_dir', type=str, required=True, default='in_audio/franklin_1_normal',
                        help='audio directory')
    args = parser.parse_args()

    audio_list = get_audio_list(args.audio_dir)
    sentences = infer_main(audio_list)

    for sentence in sentences:
        print(sentence)
