import argparse

from tqdm import tqdm

from utils import *


def get_mcs_num(label):
    print(label)
    if '_MCS_' in label:
        return label.split('_')[2]
    elif '_EXTALT' in label:
        return label.split('_')[1].split('EXTALT')[1]
    elif '_EXT' in label:
        return label.split('_')[1].split('EXT')[1]
    else:
        return label.split('_')[1].split('MCS')[1]


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
    worksheet.write(3, 5, 'GPT-4o优化')
    worksheet.write(3, 6, '中配台词')
    worksheet.set_row(3, cell_format=header_format)
    worksheet.set_column(2, 5, 70)

    row = 4
    col = 0
    for (it1, it2, it3) in tqdm(zip(audio_cn.items(), audio_cnsim.items(), audio_en.items())):
        audio, cn = it1
        _, cnsim = it2
        _, en = it3
        if isinstance(cn, list):  # 如果cn是列表(过场动画音频)
            for i in range(len(cn)):
                worksheet.write(row, col, audio)
                worksheet.write(row, col + 2, cnsim[i])
                worksheet.write(row, col + 3, cn[i])
                worksheet.write(row, col + 4, en[i])
                if chatbot is not None:
                    optimized_cnsim = chatbot.optimize(cn[i], cnsim[i], en[i])
                    worksheet.write(row, col + 5, optimized_cnsim)
                    print(optimized_cnsim)
                row += 1
        else:
            worksheet.write(row, col, audio)
            worksheet.write(row, col + 2, cnsim)
            worksheet.write(row, col + 3, cn)
            worksheet.write(row, col + 4, en)
            if chatbot is not None:
                optimized_cnsim = chatbot.optimize(cn, cnsim, en)
                worksheet.write(row, col + 5, optimized_cnsim)
                print(optimized_cnsim)
            row += 1

    workbook.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-oxt', type=str, default='fam2aud.oxt', help='oxt file path')
    parser.add_argument('-bot-opt', action='store_true', default=True, help='enable bot optimization')
    args = parser.parse_args()

    cutscene_flags_names_map = {
        '_CUT5_': 'family_2_int_seq_mastered_only',
        '_CUT7_': 'family_2_mcs_2_seq_mastered_only',
        '_CUT8_': 'family_2_mcs_3_seq_mastered_only',
        '_CUT6_': 'family_2_mcs_4_seq_mastered_only',
    }
    # audio_prefix = ['LES1A', 'LES1B']
    audio_prefix = None

    chatbot = None
    if args.bot_opt:
        chatbot = Chatbot(
            api_key='sk-TWeVsjufwEaotWqTJPVrDGXTR5GxeSmUUSmNj9Kd6IOgkVnt',
            base_url='https://api.chatanywhere.tech',
            engine='gpt-4o',
            sys_prompt='你作为专业AI助手，现在要协助我完成台词润色。我们要为GTA5这个游戏重写中文台词，目标是将原本用于阅读的中文台词改写为更适合配音的中文台词。要求：语句长度与原本的差不多；语意与原本的一致；符合GTA5的剧情；符合中国大陆本土的配音腔调。接下来会给你每句台词的原本简体中文台词和繁体中文台词作为参考，你直接给出优化后的台词内容。'
        )

    # 读取oxt文件中的字典
    labels = read_oxt(os.path.join('subtitles/label', args.oxt), audio_prefix=audio_prefix)
    cn_sub = read_oxt(os.path.join('subtitles/cn', args.oxt), audio_prefix=audio_prefix)
    cnsim_sub = read_oxt(os.path.join('subtitles/cnsim', args.oxt), audio_prefix=audio_prefix)
    en_sub = read_oxt(os.path.join('subtitles/en', args.oxt), is_cn=False, audio_prefix=audio_prefix)

    # 链接音频和台词
    audio_cnsim = link_cn_audio(labels, cutscene_flags_names_map)

    # 链接音频和台词的其他版本
    audio_cn = link_sub_verion(audio_cnsim, cn_sub, cnsim_sub)
    audio_en = link_sub_verion(audio_cnsim, en_sub, cnsim_sub)

    # 按照key排序
    audio_cn = dict(sorted(audio_cn.items()))
    audio_cnsim = dict(sorted(audio_cnsim.items()))
    audio_en = dict(sorted(audio_en.items()))

    generate_xlsx(audio_cn, audio_cnsim, audio_en, args.oxt, cutscene_flags_names_map.values(), audio_prefix, chatbot)
