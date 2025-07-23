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


def edit_sfx_by_xlsx(args):
    xlsx_file = os.path.join(in_xlsx_root, args.xlsx)
    audio_list = []
    if args.role == '':  # 不是任务台词表，不需要过滤角色
        filter_role = None
        args.role = os.path.basename(args.in_audio).split('.')[0]
    else:  # 是任务台词表，需要过滤出本次剪辑的角色的音频
        filter_role = args.role

    audio_sub_map = read_map_from_xlsx(xlsx_file, '音频文件', '中配台词', filter_role)
    print('Audio-Sub map for debug:---------------')
    for idx, (audio_file, sub_text) in enumerate(audio_sub_map.items()):
        print(idx, audio_file, sub_text)

    if os.path.isdir(os.path.join(in_audio_root, args.in_audio)):  # 音频已经按序号顺序剪好
        audio_list = [os.path.join(in_audio_root, args.in_audio, file) for file in
                      os.listdir(os.path.join(in_audio_root, args.in_audio))]
    else:  # 音频未剪好，先分割
        audio_list = split_audio(args.in_audio, len(audio_sub_map.keys()))

    if not os.path.exists(os.path.join(out_sfx_root, args.role)):
        os.makedirs(os.path.join(out_sfx_root, args.role))
    else:
        for file in os.listdir(str(os.path.join(out_sfx_root, args.role))):
            os.remove(os.path.join(out_sfx_root, args.role, file))

    for tmp_file, audio_name in zip(audio_list, audio_sub_map.keys()):
        output_file = os.path.join(out_sfx_root, args.role, f"{audio_name}.wav")
        os.rename(tmp_file, output_file)


def edit_sfx_by_raw_audio(args):
    args.overwrite_audio_dir = os.path.join(in_audio_root, args.overwrite_audio_dir)
    overwrite_audio_files = sorted(
        [os.path.join(args.overwrite_audio_dir, file) for file in os.listdir(args.overwrite_audio_dir) if
         file.endswith('.wav')], key=natural_sort_key)
    print(overwrite_audio_files)
    audio_list = split_audio(args.in_audio, len(overwrite_audio_files))
    out_sfx_dir = os.path.basename(args.in_audio).split('.')[0]

    if not os.path.exists(os.path.join(out_sfx_root, out_sfx_dir)):
        os.makedirs(os.path.join(out_sfx_root, out_sfx_dir))
    else:
        for file in os.listdir(str(os.path.join(out_sfx_root, out_sfx_dir))):
            os.remove(os.path.join(out_sfx_root, out_sfx_dir, file))

    for tmp_file, audio_name in zip(audio_list, overwrite_audio_files):
        output_file = os.path.join(out_sfx_root, out_sfx_dir, os.path.basename(audio_name))
        os.rename(tmp_file, output_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-in-audio', type=str, default='男_白_特警_1_已剪辑', help='input raw audio file of one role')
    parser.add_argument('-role', type=str, default='', help='role name')
    parser.add_argument('-xlsx', type=str, default='s_m_y_swat_01_white_full_01.xlsx', help='input xlsx file of dubbing')
    parser.add_argument('-overwrite', action='store_true', default=False, help='overwrite existing sfx files')
    parser.add_argument('-overwrite-audio-dir', type=str, default='丹尼斯_常态_已剪辑',
                        help='directly overwrite the these sfx files')
    args = parser.parse_args()

    if args.overwrite:
        edit_sfx_by_raw_audio(args)
    else:
        edit_sfx_by_xlsx(args)
