import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor
import re
from tqdm import tqdm

from sense_voice.inference_main import rec_sentences, Sentence
from utils import Chatbot


def xlsx_gen(sentences, xlsx_name, xlsx_dir, chatbot=None):
    import xlsxwriter
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    xlsx_path = f'{xlsx_dir}/{xlsx_name}.xlsx'
    workbook = xlsxwriter.Workbook(xlsx_path)
    worksheet = workbook.add_worksheet()

    notice_format = workbook.add_format(
        {'text_wrap': True, 'valign': 'vcenter', 'bold': True, 'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
    worksheet.merge_range('A1:C2',
                          '改台词和配音之前请先听原音频\n一定要注意原本的语气\n不需要修改的台词直接填入中配台词',
                          notice_format)

    worksheet.write(0, 3, '音频文件组')
    cell_format = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
    worksheet.write(1, 3, xlsx_name, cell_format)
    worksheet.set_row(1, 100)

    worksheet.write(0, 4, '角色')
    cell_format = workbook.add_format({'text_wrap': True, 'valign': 'vcenter'})
    worksheet.write(1, 4, '', cell_format)
    worksheet.set_row(1, 30)

    header_format = workbook.add_format({'bold': True, 'bg_color': '#CCCCCC'})
    worksheet.write(3, 0, '音频文件')
    worksheet.write(3, 1, '识别英文')
    worksheet.write(3, 2, 'AI翻译简中')
    worksheet.write(3, 3, '中配台词')
    worksheet.set_row(3, cell_format=header_format)
    worksheet.set_column(0, 0, 15)
    worksheet.set_column(1, 3, 40)

    lock = threading.Lock()
    row = 4
    data_rows = []

    def process_sentence(xlsx_name, last_sentence, sentence, next_sentence, row_idx):
        file_name = sentence.get_file()
        text_en = sentence.get_text()

        if chatbot is not None:
            text_cn = chatbot.translate(xlsx_name, last_sentence, sentence, next_sentence)
            # 1. 移除"翻译后的台词"、"翻译台词"、"翻译"等字样
            text_cn = text_cn.replace("翻译后的台词", "").replace("翻译台词", "").replace("翻译", "")

            # 2. 移除冒号（中文和英文）、双引号（中文和英文）
            text_cn = (text_cn.replace("：", "").replace(":", "")
                       .replace("“", "").replace("”", "").replace('"', '').replace("'", ""))

            # 3. 移除各种括号及括号内的内容
            text_cn = re.sub(r'[（(].*?[）)]', '', text_cn)  # 中文括号和英文圆括号
            text_cn = re.sub(r'[【\[]].*?[】\]]', '', text_cn)  # 中文方括号和英文方括号

            text_cn = text_cn.strip()  # 最后去除首尾空白字符
            return row_idx, file_name, text_en, text_cn

        return row_idx, file_name, text_en, None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for i, sentence in enumerate(sentences):
            last_sentence = sentences[i - 1] if i > 0 else None
            next_sentence = sentences[i + 1] if i < len(sentences) - 1 else None
            futures.append(executor.submit(process_sentence, chatbot, last_sentence, sentence, next_sentence, row))
            row += 1

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing translations"):
            row_idx, file_name, text_en, text_cn = future.result()
            with lock:
                worksheet.write(row_idx, 0, file_name)
                worksheet.write(row_idx, 1, text_en)
                if text_cn is not None:
                    worksheet.write(row_idx, 2, text_cn)
                    print(text_cn)

    workbook.close()


prompt_template1 = """
你协助我完成台词翻译。要为GTA5这个游戏的英文语音撰写中文台词，
要求：语意与原本的一致；要符合GTA5的风格；对于你认为是脏话的原文，适度翻译为对应的中国脏话以加强口语性和生动感。要符合中国大陆本土的口语化配音风格。
本次翻译的语音属于游戏中各路NPC的语音。NPC的类型可能从音频文件名和语音识别结果中推断，
接下来会给你每句语音的英文台词(机器识别结果，可能存在谐音错误，需要鉴别)和一些标签(所属语音组、所属文件名、情绪推测、事件推测)作为情感因素参考，
以及提供这句语音前后的相邻语音内容作为参考，这些相邻内容有可能包含对话的背景信息，也有可能是其他角色的对话，但是也可能无关，请注意不要过分依赖这些内容。
你根据这些进行推断，直接给出翻译后的中文台词，不需要任何的解释。
"""
prompt_template2 = """
你协助我完成台词翻译。要为GTA5这个游戏的英文语音撰写中文台词，
要求：语意与原本的一致；要符合中国大陆本土的口语化配音风格。
本次翻译的语音属于通缉系统中的警方雷达通报，需要注意场景语境。
接下来会给你每句语音的英文台词(机器识别结果，可能存在谐音错误，需要鉴别)和一些标签(所属语音组、所属文件名、情绪推测、事件推测)作为情感因素参考，
以及提供这句语音前后的相邻语音内容作为参考，这些相邻内容有可能包含对话的背景信息，也有可能是其他角色的对话，但是也可能无关，请注意不要过分依赖这些内容。
你根据这些进行推断，直接给出翻译后的中文台词，不需要任何的解释。
"""


def process_an_audio_dir(audio_dir, xlsx_dir, xlsx_name_arg, json_path_arg, batch_size, ncpu, bot_opt,
                         gen_xlsx_from_json):
    print(f'开始识别语音文件：{audio_dir}')

    xlsx_name = os.path.basename(audio_dir) if xlsx_name_arg is None else xlsx_name_arg

    chatbot = None

    if bot_opt:
        chatbot = Chatbot(
            api_key='sk-TWeVsjufwEaotWqTJPVrDGXTR5GxeSmUUSmNj9Kd6IOgkVnt',
            base_url='https://api.chatanywhere.tech/v1',
            engine='deepseek-v3',
            sys_prompt=prompt_template1,
        )

    json_path = f'{audio_dir}.json' if json_path_arg is None else json_path_arg

    if gen_xlsx_from_json:
        with open(json_path, 'r', encoding='utf-8') as f:
            sentences = [Sentence(**sentence) for sentence in json.load(f)]
        xlsx_gen(sentences, xlsx_name, xlsx_dir, chatbot)
        return

    if os.path.exists(json_path):
        print(f'{json_path} 已存在，跳过')
        return

    sentences = rec_sentences(audio_dir, batch_size, ncpu)

    print(f'识别完成，共{len(sentences)}句。')

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump([sentence.__dict__ for sentence in sentences], f, ensure_ascii=False, indent=4)
    print(f'save rec result to {json_path}')

    xlsx_gen(sentences, xlsx_name, xlsx_dir, chatbot)
    print(f'save xlsx file to {xlsx_name}')


def audio_rec(audio_dirs, xlsx_dir, xlsx_name_arg=None, json_path_arg=None, batch_size=1, ncpu=1, glob_ncpu=1,
              bot_opt=True,
              gen_xlsx_from_json=True):
    with ThreadPoolExecutor(max_workers=glob_ncpu) as executor:
        executor.map(
            process_an_audio_dir,
            audio_dirs,
            [xlsx_dir] * len(audio_dirs),
            [xlsx_name_arg] * len(audio_dirs),
            [json_path_arg] * len(audio_dirs),
            [batch_size] * len(audio_dirs),
            [ncpu] * len(audio_dirs),
            [bot_opt] * len(audio_dirs),
            [gen_xlsx_from_json] * len(audio_dirs)
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='识别无字幕的语音并形成中配台词表')
    parser.add_argument('--audio-dir', type=str, nargs='+', default=[

    ], help='语音文件目录')
    parser.add_argument('--root-audio-dir', type=str, default='S_FULL_AMB_M.rpf',
                        help='如果audio-dir非常多，则启用此参数，指定根目录自动扫描')
    parser.add_argument('--xlsx-dir', type=str, default='./in_xlsx', help='批量处理时输出xlsx根目录')
    parser.add_argument('--batch-size', type=int, default=256, help='语音识别每批处理的语音数')
    parser.add_argument('-ncpu', type=int, default=8, help='单个音频组识别的并行cpu数量')
    parser.add_argument('-glob-ncpu', type=int, default=3, help='全局并行cpu数量')
    parser.add_argument('-bot-opt', action='store_true', default=True, help='enable bot optimization')
    parser.add_argument('--gen-xlsx-from-json', action='store_true', default=True,
                        help='generate xlsx file from json file')

    args = parser.parse_args()

    if args.audio_dir is None or len(args.audio_dir) == 0:
        args.xlsx_dir = os.path.join(args.xlsx_dir, args.root_audio_dir)
        if not os.path.exists(args.xlsx_dir):
            os.makedirs(args.xlsx_dir)

        args.root_audio_dir = os.path.join('in_audio', args.root_audio_dir)

        args.audio_dir = [os.path.join(args.root_audio_dir, a) for a in os.listdir(args.root_audio_dir) if
                          os.path.isdir(os.path.join(args.root_audio_dir, a))]
    else:
        args.audio_dir = [os.path.join('in_audio', a) for a in args.audio_dir]
    print(args.audio_dir)

    audio_rec(args.audio_dir, args.xlsx_dir, batch_size=args.batch_size, ncpu=args.ncpu, glob_ncpu=args.glob_ncpu,
              bot_opt=args.bot_opt,
              gen_xlsx_from_json=args.gen_xlsx_from_json)
