import argparse
import json
from difflib import SequenceMatcher

from utils import *


def save_json(data, json_file):
    """将数据保存为json文件"""
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def replace_text_in_file(file_path, kv_map):
    """替换文件中的原台词为中配台词"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 替换原台词为中配台词
    for orig, dub in kv_map.items():
        content = content.replace(orig, dub)

    # 将修改后的内容保存
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def calculate_similarity(str1, str2):
    # 计算两个字符串的相似度
    return SequenceMatcher(None, str1, str2).ratio()


def replace_keys_by_similarity(kv_map, ori_map, threshold=0.8):
    # 创建一个新的字典用于存储修改后的键值对
    updated_kv_map = {}

    for kv_key, kv_value in kv_map.items():
        found_match = False
        for ori_value in ori_map.values():
            # 计算匹配度
            similarity = calculate_similarity(kv_key, ori_value)
            if similarity >= threshold:
                # 如果匹配度达到阈值，将 kv_map 中的键替换为 ori_map 的键
                updated_kv_map[ori_value] = kv_value
                # if similarity < 1:
                #     print(f"替换 {kv_key} 为 {ori_value}，相似度 {similarity:.2f}")
                found_match = True
                break
        if not found_match:
            # 如果没有找到匹配的 key，保留原始 key
            updated_kv_map[kv_key] = kv_value

    return updated_kv_map


def process_oxt(oxt_file, kv_map):
    """处理oxt文件，直接读取文本内容进行替换"""

    # 读取原始 oxt 文件内容
    with open(os.path.join(ori_oxt_root, oxt_file), 'r', encoding='utf-8') as file:
        content = file.read()

    # 替换原台词为中配台词
    for orig, dub in kv_map.items():
        content = content.replace(f'~z~{orig}', f'~z~{dub}')

    # 将替换后的内容写回到文件
    output_oxt = os.path.join(out_dir, oxt_file)
    with open(output_oxt, 'w', encoding='utf-8') as file:
        file.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-xlsx', type=str, default='fam3aud.xlsx')
    parser.add_argument('-oxt', type=str, default='fam3aud.oxt')
    # parser.add_argument('-json', type=str, required=True)
    args = parser.parse_args()

    xlsx_file = os.path.join(in_xlsx_root, args.xlsx)

    # 1. 读取xlsx文件并生成kv_map
    kv_map = read_map_from_xlsx(xlsx_file)

    # 2. 将kv_map保存为json文件
    # save_json(kv_map, args.json)

    # 3. 处理oxt文件，替换内容
    process_oxt(args.oxt, kv_map)
