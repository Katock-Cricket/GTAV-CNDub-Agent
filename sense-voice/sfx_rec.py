#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/FunAudioLLM/SenseVoice). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)
import re

from funasr import AutoModel

model_dir = "ckpt"

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


class Sentence:
    def __init__(self, file, raw_str):
        pattern = r'<([^>]+)><([^>]+)><([^>]+)><([^>]+)>(.*)'
        match = re.match(pattern, raw_str)
        if match:
            self.emo = match.group(2)
            self.event = match.group(3)
            self.text = match.group(5).strip()
            self.file = file
        else:
            raise ValueError("Invalid sentence format.")

    def get_file(self):
        return self.file

    def get_emo(self):
        return emo_dict.get(self.emo)

    def get_event(self):
        return event_dict.get(self.event)

    def get_text(self):
        return self.text

    def __str__(self):
        return f"{self.get_file()} {self.get_emo()} {self.get_event()} {self.get_text()}"


model = AutoModel(
    model=model_dir,
    trust_remote_code=False,
    disable_update=True,
    # remote_code="./model.py",
    # vad_model="fsmn-vad",
    # vad_kwargs={"max_single_segment_time": 30000},
    device="cuda:0",
)


def get_audio_list(path):
    # 获取path目录下所有wav文件
    import os
    audio_list = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith('.wav'):
                audio_list.append(os.path.join(root, file))
    return audio_list


def infer_main(audio_list):
    batch_res = model.generate(
        input=audio_list,
        cache={},
        language="en",  # "zh", "en", "yue", "ja", "ko", "nospeech"
        use_itn=True,
        batch_size_s=64,
        # merge_vad=True,  #
        # merge_length_s=15,
    )
    return (Sentence(res['key'], res['text']) for res in batch_res)





if __name__ == '__main__':
    audio_list = get_audio_list(audio_dir)
    sentences = infer_main(audio_list)

    for sentence in sentences:
        print(sentence)
