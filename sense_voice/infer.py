# infer_main.py
import sys
import json
import re
from funasr import AutoModel




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


def infer_main(audio_list):
    model = AutoModel(
        model="sense_voice/ckpt",
        trust_remote_code=False,
        # disable_update=True,
        ban_emo_unk=True,
        ncpu=1,
    )

    batch_res = model.generate(
        input=audio_list,
        cache={},
        language="en",  # "zh", "en", "yue", "ja", "ko", "nospeech"
        use_itn=True,
        batch_size=1,
    )

    return [construct_sentence_from_str(res['key'], res['text']) for res in batch_res]


def main():
    # 通过命令行参数获取音频列表和batch_size
    args = json.loads(sys.argv[1])  # 获取音频列表
    batch_size = int(sys.argv[2])  # 获取batch_size

    # 调用推理函数
    sentences = infer_main(args)

    # 输出结果
    print(json.dumps([sentence.__dict__ for sentence in sentences]))


if __name__ == "__main__":
    main()
