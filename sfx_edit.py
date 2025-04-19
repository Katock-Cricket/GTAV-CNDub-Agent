import argparse
import os.path

from pydub import AudioSegment
from pydub.silence import detect_silence

from utils import *


def split_audio(audio_file, count, silent_thr=-55, min_silence_len=2000):
    audio_file = os.path.join(in_audio_root, audio_file)
    audio = AudioSegment.from_file(audio_file)
    audio_list = []

    # 临时目录
    tmp_dir = f"{out_sfx_root}/tmp_{os.path.basename(audio_file).split('.')[0]}"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)
    else:
        for file in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, file))

    # 检测静音区域，参数 min_silence_len 是静音最短持续时间（毫秒）,为该函数添加进度条
    print('Detecting silence regions...')
    silent_regions = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silent_thr, seek_step=50)
    print(f"Found {len(silent_regions) + 1} segments.")

    # 按静音区域分割音频
    for i in range(len(silent_regions) + 1):
        if i == len(silent_regions):
            end = len(audio)
        else:
            end = silent_regions[i][0]

        if i == 0:
            start = 0
        else:
            start = silent_regions[i - 1][1]

        segment = audio[start:end]
        output_tmp_audio = os.path.join(tmp_dir, f"{i}.wav")
        # 重采样到48khz，转换为单声道16位
        segment = segment.set_frame_rate(48000).set_channels(1).set_sample_width(2)
        segment.export(output_tmp_audio, format="wav")
        audio_list.append(output_tmp_audio)

    # 检查分割数量
    if len(audio_list) != count:
        raise ValueError(f"Error: {audio_file} has {len(audio_list)} segments, but {count} is expected.")

    return audio_list


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-in-audio', type=str, default='富兰克林愤怒.wav', help='input raw audio file of one role')
    parser.add_argument('-role', type=str, default='', help='role name')
    parser.add_argument('-xlsx', type=str, default='富兰克林-愤怒-台词表.xlsx', help='input xlsx file of dubbing')
    args = parser.parse_args()

    xlsx_file = os.path.join(in_xlsx_root, args.xlsx)

    audio_sub_map = read_map_from_xlsx(xlsx_file, '音频文件', '中配台词',
                                       args.role if args.role != os.path.basename(args.in_audio).split('.')[0] else
                                       os.path.basename(args.in_audio).split('.')[0])
    print('Audio-Sub map for debug:---------------')
    for idx, (audio_file, sub_text) in enumerate(audio_sub_map.items()):
        print(idx, audio_file, sub_text)

    if args.role == '':
        args.role = os.path.basename(args.in_audio).split('.')[0]

    audio_list = split_audio(args.in_audio, len(audio_sub_map.keys()))

    if not os.path.exists(os.path.join(out_sfx_root, args.role)):
        os.makedirs(os.path.join(out_sfx_root, args.role))
    else:
        for file in os.listdir(str(os.path.join(out_sfx_root, args.role))):
            os.remove(os.path.join(out_sfx_root, args.role, file))

    for tmp_file, audio_name in zip(audio_list, audio_sub_map.keys()):
        output_file = os.path.join(out_sfx_root, args.role, f"{audio_name}.wav")
        os.rename(tmp_file, output_file)
