#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/FunAudioLLM/SenseVoice). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)
import argparse
import re

from funasr import AutoModel

from .tag_dict import emo_dict, event_dict


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
        return f"{self.get_file()} {self.get_emo()} {self.get_event()} {self.get_text()}"


def get_audio_list(path):
    # 获取path目录下所有wav文件
    import os
    audio_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.wav'):
                audio_list.append(os.path.join(root, file))

    print(f"Find {len(audio_list)} audio files in {path}.")
    return audio_list


model = AutoModel(
    model="sense_voice/ckpt",
    trust_remote_code=False,
    disable_update=True,
    device="cuda:0",
    ban_emo_unk=True,
    ncpu=1,
)


def infer_main(audio_list, batch_size=1):
    batch_res = model.generate(
        input=audio_list,
        cache={},
        language="en",  # "zh", "en", "yue", "ja", "ko", "nospeech"
        use_itn=True,
        batch_size=batch_size,
    )

    return [construct_sentence_from_str(res['key'], res['text']) for res in batch_res]


def rec_sentences(audio_dir, batch_size=8):
    audio_list = get_audio_list(audio_dir)
    return infer_main(audio_list, batch_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audio_dir', type=str, required=True, default='in_audio/franklin_1_normal',
                        help='audio directory')
    args = parser.parse_args()

    audio_list = get_audio_list(args.audio_dir)
    sentences = infer_main(audio_list)

    for sentence in sentences:
        print(sentence)
