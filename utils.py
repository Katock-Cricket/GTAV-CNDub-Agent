import os
from time import sleep

import pandas as pd
from openai import OpenAI
from profanity_check import predict

in_xlsx_root = 'in_xlsx'
ori_oxt_root = 'subtitles/cnsim'
out_dir = 'out_oxt'
in_audio_root = 'in_audio'
out_sfx_root = 'out_sfx'
common_punctuation = ['.', '!', '?', '。', '！', '？', '，', '、', '：', '；', '‘', '’', '“', '”', '"', "'", '(', ')', '[',
                      ']', '{', '}', '<', '>', '—', '–', '…', '—', '‘', '’', '“', '”', '《', '》', '【', '】', '『', '』',
                      '﹃', '﹄', '〔', '〕']


def censor_bad_words(sentence):
    """
    使用 profanity-check 库检测并屏蔽脏话。
    将脏话单词的每个字母之间插入 "*"。
    """
    words = sentence.split()

    for i in range(len(words)):
        if predict([words[i]])[0]:
            censored_word = '*'.join(words[i])
            words[i] = censored_word

    censored_sentence = ' '.join(words)

    return censored_sentence


# 中文检测
def is_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False


# 从oxt文件中读取字典
def read_oxt(oxt_file, is_cn=True, audio_prefix=None):
    ret = {}
    audio_prefix = [os.path.basename(oxt_file).split('aud')[0].upper()] if audio_prefix is None else audio_prefix

    def is_audio(value):
        for prefix in audio_prefix:
            if value.startswith(prefix):
                return True
        return False

    sub_prefix = '~z~'
    with open(oxt_file, 'rb') as f:
        data = f.read().decode('utf-8')
    for line in data.split('\n'):
        if ' = ' in line:
            key, value = line.split(' = ')

            key = key.strip().replace('\t', '').replace('\n', '').replace('\r', '')
            value = value.strip().replace('\t', '').replace('\n', '').replace('\r', '')
            if value.startswith(sub_prefix) and (is_chinese(value) and is_cn or not is_cn):  # 记录了字幕的项
                ret[key] = value[len(sub_prefix):]
            elif is_audio(value):  # 记录了音频文件的项
                ret[key] = value

    return ret


def read_map_from_xlsx(xlsx_file, key='原台词简中', value='中配台词', filter_role=None):
    """读取xlsx文件，找到'原台词'和'中配台词'的对应关系"""

    # 读取整个Excel文件（包括所有行和列），不指定表头
    df = pd.read_excel(xlsx_file, header=None)

    # 初始化变量来存储找到的行和列索引
    key_col, value_col, start_row = None, None, None

    # 遍历每一行，找到包含“原台词”和“中配台词”标签的行和列
    for i, row in df.iterrows():
        for j, cell in enumerate(row):
            if cell == key:
                key_col = j
                start_row = i
            elif cell == value:
                value_col = j
                start_row = i

        # 一旦找到了两个标签所在的列，就可以退出循环
        if key_col is not None and value_col is not None:
            break

    # 如果找不到所需的列，抛出异常
    if key_col is None or value_col is None:
        raise ValueError("无法找到包含‘key’或‘value’的列，请检查文件格式。")

    # 定义一个过滤函数，检查行中是否包含指定的filter_role
    def row_filter(row):
        # 不是过滤模式
        if filter_role is None:
            return True
        # 如果row的第一个元素（音频文件名）不存在大写字母，则也过滤掉（过场动画）
        if not any(c.isupper() for c in row.values[0]):
            return False
        return filter_role in row.values

    # 从 start_row + 1 行开始，过滤并提取数据
    filtered_rows = df.iloc[start_row + 1:].apply(row_filter, axis=1)
    filtered_data = df.iloc[start_row + 1:][filtered_rows]

    # 提取过滤后的 key 和 value 列数据
    original_data = filtered_data.iloc[:, key_col].str.strip()
    dub_data = filtered_data.iloc[:, value_col].str.strip()

    # 去除空值，生成键值对映射
    kv_map = dict(zip(original_data, dub_data))

    for k, v in kv_map.items():
        # 如果value的末尾没有中文或英文标点，则添加一个句号
        if v[-1] not in common_punctuation:
            kv_map[k] = v + '。'
        # 去掉空值
        if pd.isna(v):
            kv_map[k] = k

    return kv_map


class Chatbot:
    def __init__(self, api_key, base_url, engine, sys_prompt):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.engine = engine
        self.sys_prompt = sys_prompt

    def optimize(self, cn, cnsim, en):
        query = f"原台词(简体中文): {cn}\n原台词(繁体中文): {cnsim}\n原台词(英文): {en}\n请直接回复优化后的台词(简体中文):"

        retry = 0
        while retry < 10:
            try:
                completion = self.client.chat.completions.create(
                    model=self.engine,
                    messages=[
                        {"role": "system", "content": self.sys_prompt},
                        {"role": "user", "content": query},
                    ])
            except Exception as e:
                print(f"优化失败，重试{retry + 1}次。 " + str(e))
                retry += 1
                sleep(4)
                continue
            break
        if retry >= 10:
            print("优化失败，请检查问题！")
            return None

        return completion.choices[0].message.content

    def translate(self, group, file, emo, event, text):
        query = f"语音组: {group}\n文件名: {file}\n推测情绪: {emo}\n包含事件: {event}\n语音识别结果: {text}\n请直接回复翻译后的台词(简体中文):"

        retry = 0
        while retry < 10:
            try:
                completion = self.client.chat.completions.create(
                    model=self.engine,
                    messages=[
                        {"role": "system", "content": self.sys_prompt},
                        {"role": "user", "content": query},
                    ])
            except Exception as e:
                print(f"翻译失败，重试{retry+1}次。 " + str(e))
                retry += 1
                sleep(4)
                continue
            break
        if retry >= 10:
            print("翻译失败，请检查问题！")
            return None

        return completion.choices[0].message.content


if __name__ == '__main__':
    chatbot = Chatbot(
        api_key='sk-TWeVsjufwEaotWqTJPVrDGXTR5GxeSmUUSmNj9Kd6IOgkVnt',
        base_url='https://api.chatanywhere.tech',
        engine='gpt-4o',
        sys_prompt='你作为专业AI助手，现在要协助我完成台词润色。我们要为GTA这个游戏重写中文台词，目标是将原本用于阅读的中文台词改写为更适合配音的中文台词。要求：语句长度与原本的差不多；语意与原本的一致；符合GTA的风格；符合中国大陆本土的配音腔调。接下来会给你每句台词的原本简体中文台词、繁体中文台词和原英文台词作为参考，你直接给出优化后的台词内容。'
    )

    cn = '别叫我"老爸"，你个小混蛋。你最好祈祷它还能出海。'
    cnsim = '別叫我「老爸」，你這臭小子。你最好祈禱這船還可以在水上開。'
    print(chatbot.optimize(cn, cnsim))
