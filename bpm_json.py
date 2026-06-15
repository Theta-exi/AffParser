import json
import re
import fractions
frac = fractions.Fraction

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, frac):
            return f'{obj.numerator}/{obj.denominator}'
        return super.default(obj)

def custom_decoder(obj):
    if isinstance(obj, str) and ('/' in obj or '.' in obj):
        try:
            return frac(obj)
        except ValueError:
            print(f'无法解析的分数: {obj}')
    elif isinstance(obj, list):  # 递归处理列表中的元素
        return [custom_decoder(item) for item in obj]
    elif isinstance(obj, dict):  # 递归处理字典中的元素
        return {key: custom_decoder(value) for key, value in obj.items()}
    return obj

data = {
  "We're All Gonna Die": {
    "max_split": [96],
    "bpm": [[180,-1]]
  },
  "Astral Quantization": {
    "max_split": [96],
    "bpm": [[185,-1]]
  },
  "Tempestissimo": {
    "max_split": [96],
    "bpm": [[231,-1]]
  },
  "Pentiment": {
    "max_split": [96],
    "bpm": [[222,135],[210,2],[200,3],[222,-1]]
  },
  "Arcana Eden": {
    "max_split": [96,[[119145,120282],70]],
    "bpm": [[211,-1]]
  },
  "Testify": {
    "max_split": [96],
    "bpm": [[178,-1]]
  },
  "Designant.": {
    "max_split": [96],
    "bpm": [[200,69],[180,1],[170,1],[150,frac(1,2)],[130,frac(1,2)],[100,1],
            [90,frac(1,4)],[95,frac(1,4)],[100,frac(1,4)],[105,frac(1,4)],
            [110,frac(1,4)],[115,frac(1,4)],[120,frac(1,4)],[130,frac(1,4)],
            [140,8],[150,2],[155,2],[160,2],[165,2],
            [170,frac(1,2)],[175,frac(1,2)],[180,frac(1,2)],[185,frac(1,2)],
            [190,frac(1,2)],[195,frac(1,2)],[200,frac(1,2)],[205,frac(1,2)],
            [210,frac(1,2)],[215,frac(1,2)],[220,frac(1,2)],[225,frac(1,2)],
            [230,frac(1,2)],[235,frac(1,2)],[240,frac(1,2)],[245,frac(1,2)],
            [250,frac(1,2)],[255,frac(1,2)],[260,frac(1,2)],[265,frac(1,2)],
            [270,frac(1,2)],[275,frac(1,2)],[280,frac(1,2)],[285,frac(1,2)],
            [290,frac(1,4)],[295,frac(1,4)],[300,frac(1,4)],[305,frac(1,4)],
            [310,frac(1,4)],[315,frac(1,4)],[320,frac(1,4)],[325,frac(1,4)],
            [330,frac(1,4)],[335,frac(1,4)],[340,frac(1,4)],[345,frac(1,4)],
            [350,4],[200,3],[100,frac(1,4)],[110,frac(1,4)],[120,frac(1,4)],[130,frac(1,4)],
            [140,frac(1,8)],[150,frac(1,8)],[160,frac(1,8)],[170,frac(1,8)],
            [180,frac(1,8)],[185,frac(1,8)],[190,frac(1,8)],[195,frac(1,8)],[200,-1]]
  },
  "ω4": {
    "max_split": [96],
    "bpm": [[90,7],[71,1],[192,-1]]
  },
  "Vulcānus": {
    "max_split": [96],
    "bpm": [[212,-1]]
  },
  "ViRTUS": {
    "max_split": [96],
    "bpm": [[225,-1]]
  },
  "Breach of Faith": {
    "max_split": [96,[[156670,156801],frac(128,3)],[[156888,157717],64]],
    "bpm": [[172,-1]]
  },
  "And Revive The Melody": {
    "max_split": [96],
    "bpm": [[200,2],[220,20],[215,16],[210,8],[215,10],[220,16],[215,8],[210,4],
            [220,frac(17,4)],[180,frac(15,4)],[220,frac(61,16)],[210,frac(10,8)],
            [215,frac(10,8)],[220,2],[225,frac(6,4)],[180,frac(1,4)],[140,4],
            [215,8],[220,frac(51,2)],[210,2],[200,1],[190,frac(6,4)],[210,-1]]
  },
  "MEGALOVANIA (Camellia Remix)": {
    "max_split": [96],
    "bpm": [[242,-1]]
  },
  "Spider's Thread": {
    "max_split": [96],
    "bpm": [[180,-1]]
  },
  "Dantalion": {
    "max_split": [96],
    "bpm": [[186,-1]]
  },
  "Meta-Mysteria": {
    "max_split": [96],
    "bpm": [[205,-1]]
  },
  "BUCHiGiRE Berserker": {
    "max_split": [96],
    "bpm": [[200,-1]]
  }
}
a = str(data)

def format_json(obj, indent=0, max_length=100):
    """自定义 JSON 格式化：列表默认压缩到一行，超长时换行缩进。"""
    sp = '  ' * indent
    inner_sp = '  ' * (indent + 1)

    if isinstance(obj, dict):
        if not obj:
            return '{}'
        items = []
        for k, v in obj.items():
            k_str = json.dumps(k, ensure_ascii=False)
            v_str = format_json(v, indent + 1, max_length)
            items.append(f'{inner_sp}{k_str}: {v_str}')
        return '{\n' + ',\n'.join(items) + f'\n{sp}}}'

    elif isinstance(obj, list):
        if not obj:
            return '[]'

        # 先递归格式化每个元素
        item_strs = [format_json(item, indent + 1, max_length) for item in obj]
        # 尝试压缩到一行
        compact = '[' + ', '.join(item_strs) + ']'
        if len(sp + compact) <= max_length:
            return compact

        # 超长则贪心换行
        lines = ['[']
        cur_line = inner_sp
        first = True
        for i, item in enumerate(item_strs):
            sep = '' if first else ' '
            comma = ',' if i < len(item_strs) - 1 else ''
            seg = sep + item + comma
            if not first and len(cur_line + seg) > max_length:
                lines.append(cur_line)
                cur_line = inner_sp + item + comma
            else:
                cur_line += seg
            first = False
        if cur_line.strip():
            lines.append(cur_line)
        lines.append(f'{sp}]')
        return '\n'.join(lines)

    elif isinstance(obj, frac):
        return json.dumps(f'{obj.numerator}/{obj.denominator}', ensure_ascii=False)

    elif isinstance(obj, bool):
        return 'true' if obj else 'false'

    elif isinstance(obj, (int, float)):
        return json.dumps(obj)

    elif obj is None:
        return 'null'

    else:
        return json.dumps(obj, ensure_ascii=False)


# 使用自定义格式化器写入 JSON
json_str = format_json(data)

with open('bpm_data.json', 'w', encoding='utf-8') as f:
    f.write(json_str)

with open('bpm_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f, object_hook=custom_decoder)
# print(data)
print(a == str(data))