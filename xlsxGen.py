import argparse
import shutil

from tqdm import tqdm

from sfx_rec import audio_rec
from utils import *


class Script:
    def __init__(self, filename, cnsim, cn, en):
        self.filename = filename
        self.cnsim = cnsim
        self.cn = cn
        self.en = en

    def get_filename(self):
        return self.filename

    def get_cnsim(self):
        return self.cnsim

    def get_cn(self):
        return self.cn

    def get_en(self):
        return self.en

    def __str__(self):
        return f'音频文件名: {self.filename}，简体中文台词: {self.cn}，繁体中文台词: {self.cnsim}，英文台词: {self.en}'


def is_cutscene_label(label, cutscene_map):
    for flag in cutscene_map.keys():
        if flag in label:
            return cutscene_map[flag]
    return False


def is_single_audio(key, labels):
    proposed_audio_key = key + "A"
    return proposed_audio_key in labels.keys()


def link_cn_audio(labels, cutscene_map):
    ret = {}

    for key, value in labels.items():
        if is_chinese(value) and not key.startswith('0x'):
            cutscene_name = is_cutscene_label(key, cutscene_map)
            if cutscene_name:  # 过场动画音频
                audio_filename = cutscene_name
                if audio_filename not in ret:
                    ret[audio_filename] = []
                ret[audio_filename].append(value)
            elif is_single_audio(key, labels):  # 单独的音频
                audio_key = key + "A"
                audio_filename = labels[audio_key] + '_01'
                ret[audio_filename] = value
            else:  # 多个音频
                audio_key = '_'.join(key.split('_')[:-1]) + "A"
                label_postfix = key.split('_')[-1]
                audio_filename = labels[audio_key] + '_' + label_postfix
                ret[audio_filename] = value

    return ret


def link_sub_verion(audio_cnsim, sub_ver1, sub_ver2):
    ret = {}
    for audio, cnsim in audio_cnsim.items():
        # 找到cnsim_sub中value=cnsim的key
        if isinstance(cnsim, list):  # 如果cnsim是列表(过场动画音频)
            ret[audio] = []
            for cnsim_item in cnsim:
                hex_key = None
                for key, value in sub_ver2.items():
                    if value == cnsim_item:
                        hex_key = key
                        break
                if hex_key is None:
                    raise ValueError("Cannot find key for cnsim value: {}".format(cnsim))

                ver1 = sub_ver1[hex_key]
                ret[audio].append(ver1)
        else:
            hex_key = None
            for key, value in sub_ver2.items():
                if value == cnsim:
                    hex_key = key
                    break
            if hex_key is None:
                raise ValueError("Cannot find key for cnsim value: {}".format(cnsim))

            ver1 = sub_ver1[hex_key]
            ret[audio] = ver1

    return ret


# 生成xlsx表格
def generate_xlsx(audio_cn, audio_cnsim, audio_en, oxt_name, cutscene_names, sfx_names, chatbot):
    import xlsxwriter
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    xlsx_root = 'in_xlsx'
    oxt_name = os.path.basename(oxt_name).split('.')[0]
    workbook = xlsxwriter.Workbook(os.path.join(xlsx_root, oxt_name + '.xlsx'))
    worksheet = workbook.add_worksheet()

    notice_format = workbook.add_format(
        {'text_wrap': True, 'valign': 'vcenter', 'bold': True, 'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
    worksheet.merge_range('A1:C2',
                          '改台词和配音之前请先听原音频\n理解原本的语境\n顺便把“角色”这一列补全\n不需要修改的台词转换为简中填入中配台词',
                          notice_format)

    worksheet.write(0, 3, '过场动画文件')
    cell_format = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
    fill = ''
    for cutscene_name in cutscene_names:
        fill += cutscene_name + '\n'
    worksheet.write(1, 3, fill, cell_format)
    worksheet.set_row(1, 100)

    worksheet.write(0, 4, '非过场动画文件')
    cell_format = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
    if sfx_names:
        fill = ''
        for sfx_name in sfx_names:
            fill += sfx_name + '\n'
        worksheet.write(1, 4, fill, cell_format)
        worksheet.set_row(1, 100)

    header_format = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC'})
    worksheet.write(3, 0, '音频文件')
    worksheet.write(3, 1, '角色')
    worksheet.write(3, 2, '原台词简中')
    worksheet.write(3, 3, '原台词繁中')
    worksheet.write(3, 4, '原台词英文')
    worksheet.write(3, 5, 'AI优化')
    worksheet.write(3, 6, '中配台词')
    worksheet.set_row(3, cell_format=header_format)
    worksheet.set_column(0, 0, 15)
    worksheet.set_column(1, 1, 10)
    worksheet.set_column(2, 6, 37)

    lock = threading.Lock()
    row = 4

    def process_item(last_script: Script, cur_script: Script, next_script: Script, row_idx):
        audio = cur_script.get_filename()
        cnsim = cur_script.get_cnsim()
        cn = cur_script.get_cn()
        en = cur_script.get_en()

        if chatbot is not None:
            optimized_cnsim = chatbot.optimize(last_script, cur_script, next_script)
            return row_idx, audio, cnsim, cn, en, optimized_cnsim
        return row_idx, audio, cnsim, cn, en, None

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = []

        items = list(zip(audio_cn.items(), audio_cnsim.items(), audio_en.items()))

        for i in range(len(items)):
            it1, it2, it3 = items[i]
            audio, cn = it1
            _, cnsim = it2
            _, en = it3

            if isinstance(cn, list):
                for j in range(len(cn)):
                    cur_script = Script(audio, cnsim[j], cn[j], en[j])
                    last_script = Script(audio, cnsim[j-1], cn[j-1], en[j-1]) if j > 0 else None
                    next_script = Script(audio, cnsim[j+1], cn[j+1], en[j+1]) if j < len(cn)-1 else None
                    futures.append(executor.submit(process_item, last_script, cur_script, next_script, row))
                    row += 1
            else:
                cur_script = Script(audio, cnsim, cn, en)
                last_script = Script(items[i-1][0][0], items[i-1][1][1], items[i-1][0][1], items[i-1][2][1]) if i > 0 else None
                next_script = Script(items[i+1][0][0], items[i+1][1][1], items[i+1][0][1], items[i+1][2][1]) if i < len(items)-1 else None
                futures.append(executor.submit(process_item, last_script, cur_script, next_script, row))
                row += 1


        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing AI optimization"):
            row_idx, audio, cnsim, cn, en, optimized_cnsim = future.result()
            with lock:
                worksheet.write(row_idx, 0, audio.upper())
                worksheet.write(row_idx, 2, cnsim)
                worksheet.write(row_idx, 3, cn)
                worksheet.write(row_idx, 4, en)
                if optimized_cnsim is not None:
                    worksheet.write(row_idx, 5, optimized_cnsim)
                    print(optimized_cnsim)

    workbook.close()



def get_diff(audio_list_with_sub, audio_list_all):
    # 找出audio_list_all中有，但audio_list_with_sub中没有的音频，返回列表
    diff_list = []
    for audio in audio_list_all:
        if audio not in audio_list_with_sub:
            diff_list.append(audio)
    return diff_list


audio_root = 'in_audio'
prompt_template1 = '''
你协助用户为GTA5这个游戏重写/润色中文台词，目标是将原本用于阅读的中文台词改写为更适合配音的中文台词。
要求：语句长度与原本的差不多；语意与原本的一致；符合GTA5的剧情；符合中国大陆本土的口语化配音风格。
接下来会给你每句台词的原本简体中文台词、繁体中文台词、原本的英文台词作为参考，
以及提供这句语音前后的相邻语音内容作为参考，这些相邻内容有可能包含对话的背景信息，也有可能是其他角色的对话，但是也可能无关，请注意不要过分依赖这些内容。
你直接给出优化后的台词内容，不需要任何解释，不要附加任何说明。
'''

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-oxt', type=str, nargs='+', default=['pbmnaud.oxt'], help='oxt file path')
    parser.add_argument('-bot-opt', action='store_true', default=True, help='enable bot optimization')

    parser.add_argument('--rec', action='store_true', default=False, help='enable audio recgition')
    parser.add_argument('--audio-bank', type=str, default='pbmn', help='audio bank directory if audio recgition is enabled')

    args = parser.parse_args()

    cutscene_flags_names_map = {
        '_INTRO_': 'pro_ig_1_sync_mastered_only',
    }
    # audio_prefix = ['PBMN_']
    audio_prefix = None

    chatbot = None
    if args.bot_opt:
        chatbot = Chatbot(
            api_key='sk-TWeVsjufwEaotWqTJPVrDGXTR5GxeSmUUSmNj9Kd6IOgkVnt',
            base_url='https://api.chatanywhere.tech',
            engine='deepseek-v3',
            sys_prompt=prompt_template1
        )

    for oxt in args.oxt:
        # 读取oxt文件中的字典
        labels = read_oxt(os.path.join('subtitles/label', oxt), is_cn=False, audio_prefix=audio_prefix)
        cn_sub = read_oxt(os.path.join('subtitles/cn', oxt), is_cn=False, audio_prefix=audio_prefix)
        cnsim_sub = read_oxt(os.path.join('subtitles/cnsim', oxt), is_cn=False, audio_prefix=audio_prefix)
        en_sub = read_oxt(os.path.join('subtitles/en', oxt), is_cn=False, audio_prefix=audio_prefix)

        print(labels.values())

        # 链接音频和台词
        audio_cnsim = link_cn_audio(labels, cutscene_flags_names_map)

        # 链接音频和台词的其他版本
        audio_cn = link_sub_verion(audio_cnsim, cn_sub, cnsim_sub)
        audio_en = link_sub_verion(audio_cnsim, en_sub, cnsim_sub)

        # 按照key排序
        audio_cn = dict(sorted(audio_cn.items()))
        audio_cnsim = dict(sorted(audio_cnsim.items()))
        audio_en = dict(sorted(audio_en.items()))

        generate_xlsx(audio_cn, audio_cnsim, audio_en, oxt, cutscene_flags_names_map.values(), audio_prefix, chatbot)

        if args.rec:
            print("Start audio_without_sub recognition...")
            audio_dir = os.path.join(audio_root, args.audio_bank)

            # 读取audio_dir下的wav文件名列表，不带后缀
            audio_names_all = [os.path.splitext(os.path.basename(audio_file))[0] for audio_file in os.listdir(audio_dir)
                               if audio_file.endswith('.wav')]

            diff_list = get_diff(audio_cnsim.keys(), audio_names_all)

            print("There are {} audio files without subtitles.".format(len(diff_list)))

            diff_dir = os.path.join(audio_dir, 'without_sub')
            if not os.path.exists(diff_dir):
                os.makedirs(diff_dir)

            for audio in diff_list:
                a = os.path.join(audio_dir, audio + '.wav')
                a_new = os.path.join(diff_dir, audio + '.wav')
                shutil.copy(a, a_new)

            xlsx_name = f'{oxt}_without_sub'
            json_path = os.path.join(audio_root, f'{args.audio_bank}_without_sub.json')
            audio_rec([diff_dir], xlsx_name_arg=xlsx_name, json_path_arg=json_path, batch_size=1, bot_opt=args.bot_opt,
                      gen_xlsx_from_json=True)
