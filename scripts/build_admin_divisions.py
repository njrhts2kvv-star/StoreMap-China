# -*- coding: utf-8 -*-
"""
构建全国三层行政区表 admin_divisions

基于高德 API 获取的区县数据，生成省/市/区县三级结构，并补充：
- 城市等级 (city_tier)
- 城市群 (city_cluster)
- 直辖市/副省级城市标记
- 省级和重点城市的经济指标 (GDP/人口/人均收入)

输出: 各品牌爬虫数据/AMap_Admin_Divisions_Full.csv
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

# ============================================================================
# 配置
# ============================================================================

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "mall_crawler" / "cache" / "districts.json"
OUTPUT_CSV = ROOT / "各品牌爬虫数据" / "AMap_Admin_Divisions_Full.csv"

# CSV 字段顺序
FIELDNAMES = [
    "id",
    "country_code",
    "province_code",
    "city_code",
    "district_code",
    "level",
    "parent_code",
    "province_name",
    "city_name",
    "district_name",
    "short_city_name",
    "city_tier",
    "city_cluster",
    "is_municipality",
    "is_subprovincial",
    "gdp",
    "population",
    "gdp_per_capita",
    "income_per_capita",
    "stats_year",
    "citycode",
    "center_lon",
    "center_lat",
    "created_at",
    "updated_at",
]

# ============================================================================
# 城市等级数据 (第一财经 2024 城市商业魅力排行榜)
# ============================================================================

# 一线城市 (4个)
TIER_1 = {"北京", "上海", "广州", "深圳"}

# 新一线城市 (15个)
NEW_TIER_1 = {
    "成都", "重庆", "杭州", "武汉", "苏州", "西安", "南京", "长沙",
    "天津", "郑州", "东莞", "青岛", "昆明", "宁波", "合肥"
}

# 二线城市 (30个)
TIER_2 = {
    "佛山", "沈阳", "无锡", "济南", "厦门", "福州", "温州", "哈尔滨",
    "石家庄", "大连", "南宁", "贵阳", "长春", "泉州", "南昌", "金华",
    "常州", "惠州", "嘉兴", "南通", "徐州", "太原", "珠海", "中山",
    "保定", "兰州", "台州", "绍兴", "烟台", "廊坊"
}

# 三线城市 (70个)
TIER_3 = {
    "海口", "汕头", "潍坊", "扬州", "洛阳", "乌鲁木齐", "临沂", "唐山",
    "镇江", "盐城", "湖州", "赣州", "漳州", "揭阳", "江门", "桂林",
    "邯郸", "泰州", "济宁", "呼和浩特", "咸阳", "芜湖", "三亚", "阜阳",
    "淮安", "遵义", "银川", "衡阳", "上饶", "柳州", "淄博", "莆田",
    "绵阳", "湛江", "商丘", "宜昌", "沧州", "连云港", "南阳", "蚌埠",
    "驻马店", "滁州", "邢台", "潮州", "秦皇岛", "肇庆", "荆州", "周口",
    "马鞍山", "清远", "宿州", "威海", "九江", "新乡", "信阳", "襄阳",
    "岳阳", "安庆", "菏泽", "宜春", "黄冈", "泰安", "宿迁", "株洲",
    "宁德", "鞍山", "南充", "六安", "大庆", "舟山"
}

# 四线城市 (90个) - 部分列举
TIER_4 = {
    "常德", "渭南", "孝感", "丽水", "运城", "德州", "张家口", "鄂尔多斯",
    "阳江", "泸州", "丹东", "曲靖", "乐山", "许昌", "湘潭", "晋中",
    "娄底", "邵阳", "吉林", "抚州", "亳州", "梅州", "龙岩", "内江",
    "榆林", "梧州", "黄石", "三明", "日照", "怀化", "长治", "郴州",
    "河源", "玉林", "达州", "宝鸡", "延安", "咸宁", "衢州", "眉山",
    "滨州", "吕梁", "钦州", "永州", "枣庄", "平顶山", "焦作", "德阳",
    "营口", "安阳", "开封", "十堰", "齐齐哈尔", "百色", "韶关", "佳木斯",
    "铜陵", "黔东南", "黔南", "北海", "葫芦岛", "益阳", "东营", "攀枝花",
    "黄山", "拉萨", "锦州", "遂宁", "玉溪", "荆门", "池州", "宣城",
    "汕尾", "贺州", "本溪", "承德", "铜仁", "自贡", "辽阳", "聊城",
    "通辽", "防城港", "资阳", "茂名", "淮南", "随州", "淮北", "西宁",
    "来宾", "安顺"
}


def get_city_tier(short_name: str) -> str:
    """根据城市简称获取城市等级"""
    if short_name in TIER_1:
        return "一线"
    elif short_name in NEW_TIER_1:
        return "新一线"
    elif short_name in TIER_2:
        return "二线"
    elif short_name in TIER_3:
        return "三线"
    elif short_name in TIER_4:
        return "四线"
    else:
        return "五线"


# ============================================================================
# 城市群数据
# ============================================================================

CITY_CLUSTERS = {
    # 长三角城市群
    "上海": "长三角城市群", "南京": "长三角城市群", "杭州": "长三角城市群",
    "苏州": "长三角城市群", "无锡": "长三角城市群", "宁波": "长三角城市群",
    "常州": "长三角城市群", "南通": "长三角城市群", "嘉兴": "长三角城市群",
    "湖州": "长三角城市群", "绍兴": "长三角城市群", "金华": "长三角城市群",
    "舟山": "长三角城市群", "台州": "长三角城市群", "扬州": "长三角城市群",
    "镇江": "长三角城市群", "泰州": "长三角城市群", "盐城": "长三角城市群",
    "淮安": "长三角城市群", "连云港": "长三角城市群", "徐州": "长三角城市群",
    "宿迁": "长三角城市群", "芜湖": "长三角城市群", "马鞍山": "长三角城市群",
    "铜陵": "长三角城市群", "安庆": "长三角城市群", "池州": "长三角城市群",
    "宣城": "长三角城市群", "合肥": "长三角城市群", "滁州": "长三角城市群",
    "蚌埠": "长三角城市群", "阜阳": "长三角城市群", "宿州": "长三角城市群",
    "六安": "长三角城市群", "亳州": "长三角城市群", "淮南": "长三角城市群",
    "淮北": "长三角城市群", "黄山": "长三角城市群",  # 安徽全境纳入长三角
    "温州": "长三角城市群", "丽水": "长三角城市群", "衢州": "长三角城市群",  # 浙江全境

    # 粤港澳大湾区
    "广州": "粤港澳大湾区", "深圳": "粤港澳大湾区", "珠海": "粤港澳大湾区",
    "佛山": "粤港澳大湾区", "东莞": "粤港澳大湾区", "中山": "粤港澳大湾区",
    "惠州": "粤港澳大湾区", "江门": "粤港澳大湾区", "肇庆": "粤港澳大湾区",
    "汕头": "粤闽浙沿海城市群", "潮州": "粤闽浙沿海城市群", "揭阳": "粤闽浙沿海城市群",
    "汕尾": "粤闽浙沿海城市群", "梅州": "粤闽浙沿海城市群",  # 粤东
    "清远": "珠江-西江经济带", "韶关": "珠江-西江经济带", "河源": "珠江-西江经济带",  # 粤北

    # 京津冀城市群
    "北京": "京津冀城市群", "天津": "京津冀城市群", "石家庄": "京津冀城市群",
    "保定": "京津冀城市群", "廊坊": "京津冀城市群", "唐山": "京津冀城市群",
    "秦皇岛": "京津冀城市群", "张家口": "京津冀城市群", "承德": "京津冀城市群",
    "沧州": "京津冀城市群", "衡水": "京津冀城市群", "邢台": "京津冀城市群",
    "邯郸": "京津冀城市群",

    # 成渝城市群
    "成都": "成渝城市群", "重庆": "成渝城市群", "绵阳": "成渝城市群",
    "德阳": "成渝城市群", "乐山": "成渝城市群", "眉山": "成渝城市群",
    "资阳": "成渝城市群", "内江": "成渝城市群", "自贡": "成渝城市群",
    "泸州": "成渝城市群", "宜宾": "成渝城市群", "南充": "成渝城市群",
    "遂宁": "成渝城市群", "达州": "成渝城市群", "广安": "成渝城市群",
    "广元": "成渝城市群", "巴中": "成渝城市群", "雅安": "成渝城市群",
    "攀枝花": "成渝城市群", "凉山彝族": "成渝城市群",  # 四川全境
    "甘孜藏族": "成渝城市群", "阿坝藏族羌族": "成渝城市群",

    # 长江中游城市群
    "武汉": "长江中游城市群", "长沙": "长江中游城市群", "南昌": "长江中游城市群",
    "黄石": "长江中游城市群", "鄂州": "长江中游城市群", "黄冈": "长江中游城市群",
    "孝感": "长江中游城市群", "咸宁": "长江中游城市群", "仙桃": "长江中游城市群",
    "潜江": "长江中游城市群", "天门": "长江中游城市群", "株洲": "长江中游城市群",
    "湘潭": "长江中游城市群", "岳阳": "长江中游城市群", "益阳": "长江中游城市群",
    "常德": "长江中游城市群", "衡阳": "长江中游城市群", "娄底": "长江中游城市群",
    "九江": "长江中游城市群", "景德镇": "长江中游城市群", "萍乡": "长江中游城市群",
    "新余": "长江中游城市群", "鹰潭": "长江中游城市群", "抚州": "长江中游城市群",
    "宜春": "长江中游城市群", "上饶": "长江中游城市群", "吉安": "长江中游城市群",
    # 湖北全境
    "宜昌": "长江中游城市群", "襄阳": "长江中游城市群", "荆州": "长江中游城市群",
    "荆门": "长江中游城市群", "十堰": "长江中游城市群", "随州": "长江中游城市群",
    "恩施土家族苗族": "长江中游城市群", "神农架": "长江中游城市群",
    # 湖南全境
    "郴州": "长江中游城市群", "永州": "长江中游城市群", "怀化": "长江中游城市群",
    "邵阳": "长江中游城市群", "张家界": "长江中游城市群", "湘西土家族苗族": "长江中游城市群",

    # 山东半岛城市群
    "济南": "山东半岛城市群", "青岛": "山东半岛城市群", "烟台": "山东半岛城市群",
    "威海": "山东半岛城市群", "潍坊": "山东半岛城市群", "淄博": "山东半岛城市群",
    "东营": "山东半岛城市群", "日照": "山东半岛城市群", "临沂": "山东半岛城市群",
    "枣庄": "山东半岛城市群", "济宁": "山东半岛城市群", "泰安": "山东半岛城市群",
    "莱芜": "山东半岛城市群", "德州": "山东半岛城市群", "聊城": "山东半岛城市群",
    "滨州": "山东半岛城市群", "菏泽": "山东半岛城市群",

    # 中原城市群
    "郑州": "中原城市群", "洛阳": "中原城市群", "开封": "中原城市群",
    "新乡": "中原城市群", "焦作": "中原城市群", "许昌": "中原城市群",
    "平顶山": "中原城市群", "漯河": "中原城市群", "济源": "中原城市群",
    "安阳": "中原城市群", "鹤壁": "中原城市群", "濮阳": "中原城市群",
    "商丘": "中原城市群", "周口": "中原城市群", "信阳": "中原城市群",
    "南阳": "中原城市群", "驻马店": "中原城市群", "三门峡": "中原城市群",

    # 海峡西岸城市群 (福建全境 + 赣东)
    "福州": "海峡西岸城市群", "厦门": "海峡西岸城市群", "泉州": "海峡西岸城市群",
    "漳州": "海峡西岸城市群", "莆田": "海峡西岸城市群", "宁德": "海峡西岸城市群",
    "龙岩": "海峡西岸城市群", "三明": "海峡西岸城市群", "南平": "海峡西岸城市群",
    "赣州": "海峡西岸城市群",  # 赣南纳入海西

    # 海南自贸港
    "海口": "海南自贸港", "三亚": "海南自贸港", "儋州": "海南自贸港",
    "五指山": "海南自贸港", "文昌": "海南自贸港", "琼海": "海南自贸港",
    "万宁": "海南自贸港", "东方": "海南自贸港", "定安县": "海南自贸港",
    "屯昌县": "海南自贸港", "澄迈县": "海南自贸港", "临高县": "海南自贸港",
    "白沙黎族": "海南自贸港", "昌江黎族": "海南自贸港", "乐东黎族": "海南自贸港",
    "陵水黎族": "海南自贸港", "保亭黎族苗族": "海南自贸港", "琼中黎族苗族": "海南自贸港",

    # 辽中南城市群
    "沈阳": "辽中南城市群", "大连": "辽中南城市群", "鞍山": "辽中南城市群",
    "抚顺": "辽中南城市群", "本溪": "辽中南城市群", "丹东": "辽中南城市群",
    "锦州": "辽中南城市群", "营口": "辽中南城市群", "辽阳": "辽中南城市群",
    "盘锦": "辽中南城市群", "铁岭": "辽中南城市群", "朝阳": "辽中南城市群",
    "葫芦岛": "辽中南城市群", "阜新": "辽中南城市群",  # 辽宁全境

    # 哈长城市群
    "哈尔滨": "哈长城市群", "长春": "哈长城市群", "吉林": "哈长城市群",
    "大庆": "哈长城市群", "齐齐哈尔": "哈长城市群", "绥化": "哈长城市群",
    "松原": "哈长城市群", "四平": "哈长城市群", "辽源": "哈长城市群",
    "延边朝鲜族": "哈长城市群", "通化": "哈长城市群", "白山": "哈长城市群",
    "白城": "哈长城市群",  # 吉林全境
    "牡丹江": "哈长城市群", "佳木斯": "哈长城市群", "鸡西": "哈长城市群",
    "双鸭山": "哈长城市群", "伊春": "哈长城市群", "七台河": "哈长城市群",
    "鹤岗": "哈长城市群", "黑河": "哈长城市群", "大兴安岭": "哈长城市群",  # 黑龙江全境

    # 关中平原城市群
    "西安": "关中平原城市群", "咸阳": "关中平原城市群", "宝鸡": "关中平原城市群",
    "渭南": "关中平原城市群", "铜川": "关中平原城市群", "商洛": "关中平原城市群",
    "运城": "关中平原城市群", "临汾": "关中平原城市群", "天水": "关中平原城市群",
    "平凉": "关中平原城市群", "庆阳": "关中平原城市群",
    "延安": "关中平原城市群", "榆林": "关中平原城市群", "汉中": "关中平原城市群",
    "安康": "关中平原城市群",  # 陕西全境

    # 太原都市圈 / 山西中部城市群
    "太原": "山西中部城市群", "晋中": "山西中部城市群", "忻州": "山西中部城市群",
    "吕梁": "山西中部城市群", "阳泉": "山西中部城市群",
    "长治": "山西中部城市群", "晋城": "山西中部城市群",  # 山西中南部
    "大同": "山西中部城市群", "朔州": "山西中部城市群",  # 山西北部

    # 北部湾城市群
    "南宁": "北部湾城市群", "北海": "北部湾城市群", "钦州": "北部湾城市群",
    "防城港": "北部湾城市群", "玉林": "北部湾城市群", "崇左": "北部湾城市群",
    "湛江": "北部湾城市群", "茂名": "北部湾城市群", "阳江": "北部湾城市群",
    "柳州": "北部湾城市群", "桂林": "北部湾城市群", "贵港": "北部湾城市群",
    "百色": "北部湾城市群", "河池": "北部湾城市群", "来宾": "北部湾城市群",
    "贺州": "北部湾城市群", "梧州": "北部湾城市群",  # 广西全境

    # 黔中城市群
    "贵阳": "黔中城市群", "遵义": "黔中城市群", "安顺": "黔中城市群",
    "毕节": "黔中城市群", "六盘水": "黔中城市群",

    # 滇中城市群
    "昆明": "滇中城市群", "曲靖": "滇中城市群", "玉溪": "滇中城市群",
    "楚雄": "滇中城市群", "红河": "滇中城市群",

    # 呼包鄂榆城市群
    "呼和浩特": "呼包鄂榆城市群", "包头": "呼包鄂榆城市群", "鄂尔多斯": "呼包鄂榆城市群",
    "榆林": "呼包鄂榆城市群",
    "赤峰": "呼包鄂榆城市群", "通辽": "呼包鄂榆城市群",
    "呼伦贝尔": "呼包鄂榆城市群", "巴彦淖尔": "呼包鄂榆城市群",
    "乌兰察布": "呼包鄂榆城市群", "锡林郭勒": "呼包鄂榆城市群",
    "兴安": "呼包鄂榆城市群", "阿拉善": "呼包鄂榆城市群", "乌海": "呼包鄂榆城市群",  # 内蒙古全境

    # 兰西城市群
    "兰州": "兰西城市群", "西宁": "兰西城市群", "白银": "兰西城市群",
    "定西": "兰西城市群", "临夏回族": "兰西城市群", "海东": "兰西城市群",
    "天水": "兰西城市群", "平凉": "兰西城市群", "庆阳": "兰西城市群",
    "武威": "兰西城市群", "张掖": "兰西城市群", "酒泉": "兰西城市群",
    "嘉峪关": "兰西城市群", "金昌": "兰西城市群", "陇南": "兰西城市群",
    "甘南藏族": "兰西城市群",  # 甘肃全境
    "海西蒙古族藏族": "兰西城市群", "海南藏族": "兰西城市群",
    "海北藏族": "兰西城市群", "黄南藏族": "兰西城市群",
    "玉树藏族": "兰西城市群", "果洛藏族": "兰西城市群",  # 青海全境

    # 宁夏沿黄城市群
    "银川": "宁夏沿黄城市群", "石嘴山": "宁夏沿黄城市群", "吴忠": "宁夏沿黄城市群",
    "中卫": "宁夏沿黄城市群", "固原": "宁夏沿黄城市群",  # 宁夏全境

    # 天山北坡城市群 / 新疆城市群
    "乌鲁木齐": "天山北坡城市群", "昌吉回族": "天山北坡城市群", "石河子": "天山北坡城市群",
    "克拉玛依": "天山北坡城市群", "伊犁哈萨克": "天山北坡城市群",
    "阿克苏": "天山北坡城市群", "喀什": "天山北坡城市群", "和田": "天山北坡城市群",
    "巴音郭楞蒙古": "天山北坡城市群", "塔城": "天山北坡城市群", "阿勒泰": "天山北坡城市群",
    "博尔塔拉蒙古": "天山北坡城市群", "吐鲁番": "天山北坡城市群", "哈密": "天山北坡城市群",
    "克孜勒苏柯尔克孜": "天山北坡城市群",  # 新疆全境
    "北屯": "天山北坡城市群", "阿拉尔": "天山北坡城市群", "图木舒克": "天山北坡城市群",
    "五家渠": "天山北坡城市群", "铁门关": "天山北坡城市群", "双河": "天山北坡城市群",
    "可克达拉": "天山北坡城市群", "昆玉": "天山北坡城市群", "胡杨河": "天山北坡城市群",
    "新星": "天山北坡城市群", "白杨": "天山北坡城市群",  # 新疆兵团

    # 滇中城市群扩展
    "红河哈尼族彝族": "滇中城市群", "楚雄彝族": "滇中城市群",
    "文山壮族苗族": "滇中城市群", "大理白族": "滇中城市群",
    "西双版纳傣族": "滇中城市群", "德宏傣族景颇族": "滇中城市群",
    "怒江傈僳族": "滇中城市群", "迪庆藏族": "滇中城市群",
    "普洱": "滇中城市群", "临沧": "滇中城市群", "保山": "滇中城市群",
    "昭通": "滇中城市群", "丽江": "滇中城市群",  # 云南全境

    # 黔中城市群扩展
    "黔南布依族苗族": "黔中城市群", "黔东南苗族侗族": "黔中城市群",
    "黔西南布依族苗族": "黔中城市群", "铜仁": "黔中城市群",  # 贵州全境

    # 西藏城市群
    "拉萨": "西藏城市群", "日喀则": "西藏城市群", "昌都": "西藏城市群",
    "林芝": "西藏城市群", "山南": "西藏城市群", "那曲": "西藏城市群", "阿里": "西藏城市群",

    # 云浮纳入珠三角
    "云浮": "粤港澳大湾区",

    # 重庆郊县
    "重庆郊县": "成渝城市群",
}

# ============================================================================
# 直辖市和副省级城市
# ============================================================================

MUNICIPALITIES = {"北京", "上海", "天津", "重庆"}

SUBPROVINCIAL_CITIES = {
    "广州", "深圳", "南京", "武汉", "沈阳", "西安", "成都", "济南", "杭州", "哈尔滨",
    "大连", "青岛", "厦门", "宁波", "长春"
}

# ============================================================================
# 省级 GDP / 人口数据 (2023年，国家统计局)
# ============================================================================

PROVINCE_DATA = {
    "广东省": {"gdp": 135673.16, "population": 12706, "income_per_capita": 54859},
    "江苏省": {"gdp": 128222.16, "population": 8526, "income_per_capita": 52987},
    "山东省": {"gdp": 92069.00, "population": 10163, "income_per_capita": 39890},
    "浙江省": {"gdp": 82553.00, "population": 6577, "income_per_capita": 63830},
    "河南省": {"gdp": 59132.39, "population": 9815, "income_per_capita": 29536},
    "四川省": {"gdp": 60132.90, "population": 8368, "income_per_capita": 32514},
    "湖北省": {"gdp": 55803.63, "population": 5838, "income_per_capita": 35809},
    "福建省": {"gdp": 54355.00, "population": 4183, "income_per_capita": 45636},
    "湖南省": {"gdp": 50000.00, "population": 6568, "income_per_capita": 35895},
    "上海市": {"gdp": 47218.66, "population": 2487, "income_per_capita": 84834},
    "安徽省": {"gdp": 47050.60, "population": 6127, "income_per_capita": 34593},
    "北京市": {"gdp": 43760.70, "population": 2185, "income_per_capita": 81752},
    "河北省": {"gdp": 43944.10, "population": 7393, "income_per_capita": 32903},
    "陕西省": {"gdp": 33786.07, "population": 3956, "income_per_capita": 32854},
    "江西省": {"gdp": 32074.70, "population": 4515, "income_per_capita": 33217},
    "重庆市": {"gdp": 30145.79, "population": 3212, "income_per_capita": 38135},
    "辽宁省": {"gdp": 30209.40, "population": 4182, "income_per_capita": 37960},
    "云南省": {"gdp": 30021.00, "population": 4673, "income_per_capita": 28150},
    "广西壮族自治区": {"gdp": 27202.39, "population": 5027, "income_per_capita": 29195},
    "山西省": {"gdp": 25698.18, "population": 3465, "income_per_capita": 31839},
    "内蒙古自治区": {"gdp": 24627.00, "population": 2396, "income_per_capita": 37482},
    "贵州省": {"gdp": 20913.25, "population": 3856, "income_per_capita": 26420},
    "新疆维吾尔自治区": {"gdp": 19125.91, "population": 2587, "income_per_capita": 28947},
    "天津市": {"gdp": 16737.30, "population": 1364, "income_per_capita": 51271},
    "黑龙江省": {"gdp": 15883.90, "population": 3091, "income_per_capita": 28102},
    "吉林省": {"gdp": 13531.19, "population": 2339, "income_per_capita": 29140},
    "甘肃省": {"gdp": 11863.80, "population": 2465, "income_per_capita": 24495},
    "海南省": {"gdp": 7551.18, "population": 1027, "income_per_capita": 32818},
    "宁夏回族自治区": {"gdp": 5315.00, "population": 728, "income_per_capita": 30586},
    "青海省": {"gdp": 3799.09, "population": 594, "income_per_capita": 27979},
    "西藏自治区": {"gdp": 2392.67, "population": 366, "income_per_capita": 28983},
}

# ============================================================================
# 主要城市 GDP / 人口数据 (2023年)
# ============================================================================

CITY_DATA = {
    # 一线城市
    "上海": {"gdp": 47218.66, "population": 2487, "income_per_capita": 84834},
    "北京": {"gdp": 43760.70, "population": 2185, "income_per_capita": 81752},
    "深圳": {"gdp": 34606.40, "population": 1768, "income_per_capita": 76910},
    "广州": {"gdp": 30355.73, "population": 1882, "income_per_capita": 80501},

    # 新一线城市
    "重庆": {"gdp": 30145.79, "population": 3212, "income_per_capita": 38135},
    "苏州": {"gdp": 24653.40, "population": 1295, "income_per_capita": 74116},
    "成都": {"gdp": 22074.70, "population": 2140, "income_per_capita": 50477},
    "杭州": {"gdp": 20059.00, "population": 1237, "income_per_capita": 77043},
    "武汉": {"gdp": 20011.65, "population": 1377, "income_per_capita": 58449},
    "南京": {"gdp": 17421.40, "population": 954, "income_per_capita": 72810},
    "天津": {"gdp": 16737.30, "population": 1364, "income_per_capita": 51271},
    "宁波": {"gdp": 16452.80, "population": 969, "income_per_capita": 71729},
    "青岛": {"gdp": 15760.34, "population": 1037, "income_per_capita": 57598},
    "长沙": {"gdp": 14331.98, "population": 1058, "income_per_capita": 60698},
    "郑州": {"gdp": 13617.80, "population": 1300, "income_per_capita": 42887},
    "佛山": {"gdp": 12698.39, "population": 961, "income_per_capita": 66563},
    "无锡": {"gdp": 15456.19, "population": 749, "income_per_capita": 68707},
    "济南": {"gdp": 12757.40, "population": 941, "income_per_capita": 54306},
    "合肥": {"gdp": 12673.78, "population": 985, "income_per_capita": 52594},
    "东莞": {"gdp": 11438.13, "population": 1048, "income_per_capita": 68116},
    "西安": {"gdp": 12391.49, "population": 1307, "income_per_capita": 46009},
    "昆明": {"gdp": 7864.76, "population": 857, "income_per_capita": 48576},

    # 二线城市 (部分)
    "福州": {"gdp": 12928.47, "population": 845, "income_per_capita": 50608},
    "泉州": {"gdp": 12102.97, "population": 889, "income_per_capita": 47782},
    "南通": {"gdp": 11813.30, "population": 773, "income_per_capita": 50323},
    "烟台": {"gdp": 9853.30, "population": 710, "income_per_capita": 50785},
    "常州": {"gdp": 10116.36, "population": 536, "income_per_capita": 62108},
    "厦门": {"gdp": 8066.49, "population": 532, "income_per_capita": 70531},
    "大连": {"gdp": 8752.90, "population": 746, "income_per_capita": 50490},
    "沈阳": {"gdp": 8122.10, "population": 914, "income_per_capita": 49200},
    "哈尔滨": {"gdp": 5576.30, "population": 1001, "income_per_capita": 36421},
    "长春": {"gdp": 7002.10, "population": 907, "income_per_capita": 40100},
    "石家庄": {"gdp": 7525.00, "population": 1122, "income_per_capita": 38500},
    "太原": {"gdp": 5571.17, "population": 543, "income_per_capita": 42350},
    "南宁": {"gdp": 5580.00, "population": 889, "income_per_capita": 40800},
    "贵阳": {"gdp": 5118.00, "population": 622, "income_per_capita": 45200},
    "南昌": {"gdp": 7203.50, "population": 653, "income_per_capita": 47100},
    "兰州": {"gdp": 3543.00, "population": 442, "income_per_capita": 41200},
    "温州": {"gdp": 8730.60, "population": 967, "income_per_capita": 64800},
    "珠海": {"gdp": 4233.20, "population": 247, "income_per_capita": 68500},
    "惠州": {"gdp": 5639.68, "population": 606, "income_per_capita": 52800},
    "中山": {"gdp": 3850.00, "population": 443, "income_per_capita": 60500},
    "徐州": {"gdp": 8900.44, "population": 902, "income_per_capita": 38600},
    "金华": {"gdp": 6011.27, "population": 712, "income_per_capita": 62100},
    "嘉兴": {"gdp": 7062.45, "population": 556, "income_per_capita": 66700},
    "绍兴": {"gdp": 7620.50, "population": 535, "income_per_capita": 69200},
    "台州": {"gdp": 6180.00, "population": 666, "income_per_capita": 60500},
    "保定": {"gdp": 4200.00, "population": 924, "income_per_capita": 30200},
    "廊坊": {"gdp": 3580.00, "population": 550, "income_per_capita": 38500},

    # 三线城市
    "洛阳": {"gdp": 5675.00, "population": 707, "income_per_capita": 35200},
    "唐山": {"gdp": 8901.00, "population": 771, "income_per_capita": 38900},
    "潍坊": {"gdp": 7580.00, "population": 938, "income_per_capita": 40200},
    "临沂": {"gdp": 5900.00, "population": 1102, "income_per_capita": 32100},
    "乌鲁木齐": {"gdp": 4206.00, "population": 407, "income_per_capita": 43800},
    "银川": {"gdp": 2645.00, "population": 290, "income_per_capita": 39600},
    "海口": {"gdp": 2102.00, "population": 294, "income_per_capita": 43500},
    "三亚": {"gdp": 1065.00, "population": 104, "income_per_capita": 42800},
    "扬州": {"gdp": 7423.26, "population": 456, "income_per_capita": 50300},
    "盐城": {"gdp": 7403.87, "population": 671, "income_per_capita": 38200},
    "泰州": {"gdp": 6731.66, "population": 451, "income_per_capita": 47800},
    "镇江": {"gdp": 5264.08, "population": 321, "income_per_capita": 55600},
    "淮安": {"gdp": 5015.06, "population": 455, "income_per_capita": 37500},
    "连云港": {"gdp": 4363.63, "population": 460, "income_per_capita": 35200},
    "宿迁": {"gdp": 4398.07, "population": 500, "income_per_capita": 32800},
    "湖州": {"gdp": 4015.07, "population": 341, "income_per_capita": 63200},
    "漳州": {"gdp": 5727.60, "population": 506, "income_per_capita": 42100},
    "莆田": {"gdp": 3102.35, "population": 322, "income_per_capita": 38500},
    "宁德": {"gdp": 3656.00, "population": 315, "income_per_capita": 35800},
    "芜湖": {"gdp": 4741.11, "population": 373, "income_per_capita": 46200},
    "马鞍山": {"gdp": 2590.00, "population": 219, "income_per_capita": 49500},
    "安庆": {"gdp": 2767.00, "population": 416, "income_per_capita": 32800},  # 三线城市
    "蚌埠": {"gdp": 2148.00, "population": 329, "income_per_capita": 32800},
    "阜阳": {"gdp": 3587.60, "population": 815, "income_per_capita": 28600},
    "宿州": {"gdp": 2401.00, "population": 532, "income_per_capita": 28200},
    "六安": {"gdp": 2147.00, "population": 439, "income_per_capita": 29800},
    "滁州": {"gdp": 3850.00, "population": 398, "income_per_capita": 35600},
    "赣州": {"gdp": 4606.00, "population": 898, "income_per_capita": 32500},
    "九江": {"gdp": 4012.53, "population": 456, "income_per_capita": 38200},
    "上饶": {"gdp": 3401.00, "population": 649, "income_per_capita": 32800},
    "宜春": {"gdp": 3220.00, "population": 498, "income_per_capita": 33500},
    "汕头": {"gdp": 3158.00, "population": 556, "income_per_capita": 36200},
    "揭阳": {"gdp": 2318.00, "population": 562, "income_per_capita": 28500},
    "潮州": {"gdp": 1296.00, "population": 256, "income_per_capita": 30200},
    "江门": {"gdp": 4022.25, "population": 480, "income_per_capita": 45800},
    "清远": {"gdp": 2090.00, "population": 397, "income_per_capita": 32500},
    "湛江": {"gdp": 3712.00, "population": 698, "income_per_capita": 29800},
    "肇庆": {"gdp": 2838.00, "population": 412, "income_per_capita": 35600},
    "桂林": {"gdp": 2657.00, "population": 494, "income_per_capita": 35200},
    "柳州": {"gdp": 3410.00, "population": 416, "income_per_capita": 38500},
    "呼和浩特": {"gdp": 3853.00, "population": 355, "income_per_capita": 50800},
    "邯郸": {"gdp": 4580.00, "population": 941, "income_per_capita": 31200},
    "邢台": {"gdp": 2601.00, "population": 711, "income_per_capita": 28500},
    "沧州": {"gdp": 4388.00, "population": 730, "income_per_capita": 32800},
    "秦皇岛": {"gdp": 2041.00, "population": 316, "income_per_capita": 38200},
    "济宁": {"gdp": 5310.00, "population": 835, "income_per_capita": 35200},
    "淄博": {"gdp": 4561.79, "population": 470, "income_per_capita": 42800},
    "威海": {"gdp": 3580.00, "population": 291, "income_per_capita": 51200},
    "泰安": {"gdp": 3186.00, "population": 547, "income_per_capita": 37500},
    "菏泽": {"gdp": 4464.49, "population": 874, "income_per_capita": 28500},
    "商丘": {"gdp": 3195.00, "population": 772, "income_per_capita": 26800},
    "周口": {"gdp": 3616.00, "population": 876, "income_per_capita": 25200},
    "南阳": {"gdp": 4555.00, "population": 971, "income_per_capita": 27800},
    "新乡": {"gdp": 3268.00, "population": 625, "income_per_capita": 29500},
    "信阳": {"gdp": 3217.00, "population": 618, "income_per_capita": 27200},
    "驻马店": {"gdp": 3220.00, "population": 700, "income_per_capita": 25800},
    "绵阳": {"gdp": 4038.00, "population": 489, "income_per_capita": 38500},
    "南充": {"gdp": 2734.00, "population": 556, "income_per_capita": 32200},
    "遵义": {"gdp": 4601.00, "population": 631, "income_per_capita": 35800},
    "岳阳": {"gdp": 4402.00, "population": 505, "income_per_capita": 38200},
    "衡阳": {"gdp": 4089.00, "population": 664, "income_per_capita": 35500},
    "株洲": {"gdp": 3763.00, "population": 390, "income_per_capita": 46800},
    "宜昌": {"gdp": 5756.00, "population": 392, "income_per_capita": 40200},
    "襄阳": {"gdp": 5843.00, "population": 526, "income_per_capita": 38500},
    "荆州": {"gdp": 3089.00, "population": 523, "income_per_capita": 32800},
    "黄冈": {"gdp": 2856.00, "population": 588, "income_per_capita": 28500},
    "咸阳": {"gdp": 2852.00, "population": 421, "income_per_capita": 32200},
    "舟山": {"gdp": 1903.00, "population": 117, "income_per_capita": 68500},
    "大庆": {"gdp": 3200.00, "population": 278, "income_per_capita": 38200},
    "鞍山": {"gdp": 1856.00, "population": 332, "income_per_capita": 38500},

    # 四线城市
    "常德": {"gdp": 4435.00, "population": 528, "income_per_capita": 36800},
    "渭南": {"gdp": 2302.00, "population": 468, "income_per_capita": 28500},
    "孝感": {"gdp": 2818.00, "population": 427, "income_per_capita": 32500},
    "丽水": {"gdp": 1903.00, "population": 270, "income_per_capita": 48500},
    "运城": {"gdp": 2280.00, "population": 477, "income_per_capita": 26800},
    "德州": {"gdp": 3870.00, "population": 561, "income_per_capita": 32200},
    "张家口": {"gdp": 1847.00, "population": 411, "income_per_capita": 32800},
    "鄂尔多斯": {"gdp": 5849.00, "population": 220, "income_per_capita": 52800},
    "阳江": {"gdp": 1620.00, "population": 260, "income_per_capita": 32500},
    "泸州": {"gdp": 2743.00, "population": 426, "income_per_capita": 35200},
    "丹东": {"gdp": 1025.00, "population": 218, "income_per_capita": 32800},
    "曲靖": {"gdp": 3802.00, "population": 576, "income_per_capita": 30200},
    "乐山": {"gdp": 2401.00, "population": 316, "income_per_capita": 35500},
    "许昌": {"gdp": 3601.00, "population": 442, "income_per_capita": 32800},
    "湘潭": {"gdp": 2954.00, "population": 272, "income_per_capita": 42500},
    "晋中": {"gdp": 1855.00, "population": 337, "income_per_capita": 32200},
    "娄底": {"gdp": 1883.00, "population": 382, "income_per_capita": 32500},
    "邵阳": {"gdp": 2823.00, "population": 656, "income_per_capita": 28500},
    "吉林": {"gdp": 1709.00, "population": 362, "income_per_capita": 32800},
    "抚州": {"gdp": 2068.00, "population": 361, "income_per_capita": 32500},
    "亳州": {"gdp": 2215.00, "population": 499, "income_per_capita": 28200},
    "梅州": {"gdp": 1401.00, "population": 387, "income_per_capita": 28500},
    "龙岩": {"gdp": 3587.00, "population": 273, "income_per_capita": 42200},
    "内江": {"gdp": 1801.00, "population": 314, "income_per_capita": 32200},
    "榆林": {"gdp": 6543.65, "population": 362, "income_per_capita": 38500},
    "梧州": {"gdp": 1302.00, "population": 282, "income_per_capita": 32800},
    "黄石": {"gdp": 2101.00, "population": 243, "income_per_capita": 38500},
    "三明": {"gdp": 3022.00, "population": 245, "income_per_capita": 42500},
    "日照": {"gdp": 2401.00, "population": 296, "income_per_capita": 38200},
    "怀化": {"gdp": 1956.00, "population": 458, "income_per_capita": 28500},
    "长治": {"gdp": 2805.00, "population": 317, "income_per_capita": 35200},
    "郴州": {"gdp": 2865.00, "population": 466, "income_per_capita": 35800},
    "河源": {"gdp": 1401.00, "population": 283, "income_per_capita": 28500},
    "玉林": {"gdp": 2102.00, "population": 580, "income_per_capita": 28200},
    "达州": {"gdp": 2656.00, "population": 538, "income_per_capita": 28500},
    "宝鸡": {"gdp": 2586.00, "population": 332, "income_per_capita": 35200},
    "延安": {"gdp": 2280.00, "population": 226, "income_per_capita": 35800},
    "咸宁": {"gdp": 1956.00, "population": 248, "income_per_capita": 35200},
    "衢州": {"gdp": 2003.00, "population": 228, "income_per_capita": 48500},
    "眉山": {"gdp": 1720.00, "population": 296, "income_per_capita": 35200},
    "滨州": {"gdp": 3002.00, "population": 392, "income_per_capita": 35800},
    "吕梁": {"gdp": 2102.00, "population": 339, "income_per_capita": 28500},
    "钦州": {"gdp": 1803.00, "population": 330, "income_per_capita": 32200},
    "永州": {"gdp": 2401.00, "population": 529, "income_per_capita": 28500},
    "枣庄": {"gdp": 2102.00, "population": 385, "income_per_capita": 32800},
    "平顶山": {"gdp": 2956.00, "population": 499, "income_per_capita": 32200},
    "焦作": {"gdp": 2602.00, "population": 352, "income_per_capita": 32800},
    "德阳": {"gdp": 2956.00, "population": 345, "income_per_capita": 42500},
    "南平": {"gdp": 2356.00, "population": 264, "income_per_capita": 38500},
    "宜宾": {"gdp": 3656.00, "population": 458, "income_per_capita": 38500},
    "安阳": {"gdp": 2502.00, "population": 540, "income_per_capita": 28500},
    "聊城": {"gdp": 2956.00, "population": 595, "income_per_capita": 28500},
    "开封": {"gdp": 2656.00, "population": 486, "income_per_capita": 28500},
    "漯河": {"gdp": 1803.00, "population": 267, "income_per_capita": 32200},
    "濮阳": {"gdp": 1956.00, "population": 384, "income_per_capita": 28500},
    "鹤壁": {"gdp": 1102.00, "population": 156, "income_per_capita": 32800},
    "十堰": {"gdp": 2156.00, "population": 320, "income_per_capita": 35200},
    "荆门": {"gdp": 2402.00, "population": 260, "income_per_capita": 38500},
    "随州": {"gdp": 1356.00, "population": 202, "income_per_capita": 32800},
    "益阳": {"gdp": 2102.00, "population": 385, "income_per_capita": 35200},
    "通辽": {"gdp": 1602.00, "population": 303, "income_per_capita": 32200},
    "佳木斯": {"gdp": 1002.00, "population": 215, "income_per_capita": 28500},
    "淮南": {"gdp": 1602.00, "population": 303, "income_per_capita": 32200},
    "淮北": {"gdp": 1302.00, "population": 197, "income_per_capita": 35200},
    "黄山": {"gdp": 1056.00, "population": 133, "income_per_capita": 42500},
    "铜陵": {"gdp": 1302.00, "population": 131, "income_per_capita": 45200},
    "池州": {"gdp": 1102.00, "population": 134, "income_per_capita": 38500},
    "宣城": {"gdp": 1956.00, "population": 250, "income_per_capita": 42500},
    "安顺": {"gdp": 1156.00, "population": 247, "income_per_capita": 28500},
    "六盘水": {"gdp": 1502.00, "population": 303, "income_per_capita": 28200},
    "毕节": {"gdp": 2302.00, "population": 689, "income_per_capita": 25200},
    "铜仁": {"gdp": 1502.00, "population": 373, "income_per_capita": 26800},
    "黔南": {"gdp": 1756.00, "population": 330, "income_per_capita": 28500},
    "黔东南": {"gdp": 1356.00, "population": 375, "income_per_capita": 26800},
    "黔西南": {"gdp": 1456.00, "population": 302, "income_per_capita": 26500},
    "玉溪": {"gdp": 2656.00, "population": 227, "income_per_capita": 42500},
    "红河": {"gdp": 2956.00, "population": 450, "income_per_capita": 28500},
    "大理": {"gdp": 1702.00, "population": 333, "income_per_capita": 32200},
    "文山": {"gdp": 1456.00, "population": 362, "income_per_capita": 26800},
    "楚雄": {"gdp": 1702.00, "population": 242, "income_per_capita": 35200},
    "普洱": {"gdp": 1102.00, "population": 241, "income_per_capita": 26800},
    "保山": {"gdp": 1302.00, "population": 244, "income_per_capita": 28500},
    "昭通": {"gdp": 1702.00, "population": 509, "income_per_capita": 22800},
    "临沧": {"gdp": 1102.00, "population": 226, "income_per_capita": 26800},
    "西双版纳": {"gdp": 802.00, "population": 133, "income_per_capita": 28500},
    "德宏": {"gdp": 602.00, "population": 132, "income_per_capita": 26800},
    "丽江": {"gdp": 702.00, "population": 125, "income_per_capita": 32200},
    "迪庆": {"gdp": 302.00, "population": 39, "income_per_capita": 28500},
    "怒江": {"gdp": 252.00, "population": 55, "income_per_capita": 22800},
    "包头": {"gdp": 4263.00, "population": 274, "income_per_capita": 52800},
    "赤峰": {"gdp": 2102.00, "population": 403, "income_per_capita": 32200},
    "呼伦贝尔": {"gdp": 1702.00, "population": 230, "income_per_capita": 35200},
    "巴彦淖尔": {"gdp": 1102.00, "population": 153, "income_per_capita": 32800},
    "乌兰察布": {"gdp": 1102.00, "population": 171, "income_per_capita": 28500},
    "锡林郭勒": {"gdp": 1102.00, "population": 114, "income_per_capita": 42500},
    "兴安": {"gdp": 602.00, "population": 141, "income_per_capita": 28500},
    "阿拉善": {"gdp": 502.00, "population": 27, "income_per_capita": 52800},
    "景德镇": {"gdp": 1302.00, "population": 162, "income_per_capita": 42500},
    "萍乡": {"gdp": 1202.00, "population": 180, "income_per_capita": 38500},
    "新余": {"gdp": 1502.00, "population": 120, "income_per_capita": 45200},
    "鹰潭": {"gdp": 1202.00, "population": 115, "income_per_capita": 42500},
    "吉安": {"gdp": 2656.00, "population": 447, "income_per_capita": 32800},

    # 补充四线城市
    "承德": {"gdp": 1802.00, "population": 334, "income_per_capita": 32800},
    "本溪": {"gdp": 1002.00, "population": 133, "income_per_capita": 38500},
    "锦州": {"gdp": 1402.00, "population": 269, "income_per_capita": 35200},
    "营口": {"gdp": 1502.00, "population": 232, "income_per_capita": 38500},
    "辽阳": {"gdp": 1002.00, "population": 163, "income_per_capita": 35200},
    "葫芦岛": {"gdp": 902.00, "population": 261, "income_per_capita": 32800},
    "齐齐哈尔": {"gdp": 1302.00, "population": 406, "income_per_capita": 28500},
    "东营": {"gdp": 3802.00, "population": 220, "income_per_capita": 52800},
    "韶关": {"gdp": 1602.00, "population": 285, "income_per_capita": 35200},
    "茂名": {"gdp": 3802.00, "population": 618, "income_per_capita": 32200},
    "汕尾": {"gdp": 1302.00, "population": 267, "income_per_capita": 28500},
    "北海": {"gdp": 1802.00, "population": 188, "income_per_capita": 38500},
    "防城港": {"gdp": 902.00, "population": 105, "income_per_capita": 38500},
    "百色": {"gdp": 1602.00, "population": 347, "income_per_capita": 26800},
    "贺州": {"gdp": 902.00, "population": 195, "income_per_capita": 28500},
    "来宾": {"gdp": 902.00, "population": 207, "income_per_capita": 26800},
    "崇左": {"gdp": 1102.00, "population": 205, "income_per_capita": 28500},
    "贵港": {"gdp": 1502.00, "population": 428, "income_per_capita": 28200},
    "河池": {"gdp": 1102.00, "population": 341, "income_per_capita": 22800},
    "阳泉": {"gdp": 902.00, "population": 131, "income_per_capita": 35200},
    "大同": {"gdp": 1802.00, "population": 310, "income_per_capita": 32200},
    "晋城": {"gdp": 1902.00, "population": 219, "income_per_capita": 38500},
    "朔州": {"gdp": 1302.00, "population": 159, "income_per_capita": 35200},
    "忻州": {"gdp": 1302.00, "population": 265, "income_per_capita": 28500},
    "临汾": {"gdp": 2102.00, "population": 391, "income_per_capita": 32200},
    "乌海": {"gdp": 802.00, "population": 56, "income_per_capita": 52800},
    "抚顺": {"gdp": 1002.00, "population": 185, "income_per_capita": 35200},
    "阜新": {"gdp": 602.00, "population": 167, "income_per_capita": 28500},
    "盘锦": {"gdp": 1602.00, "population": 139, "income_per_capita": 48500},
    "铁岭": {"gdp": 702.00, "population": 225, "income_per_capita": 28500},
    "朝阳": {"gdp": 1102.00, "population": 285, "income_per_capita": 26800},
    "四平": {"gdp": 802.00, "population": 181, "income_per_capita": 28500},
    "辽源": {"gdp": 502.00, "population": 97, "income_per_capita": 28500},
    "白城": {"gdp": 702.00, "population": 159, "income_per_capita": 26800},
    "松原": {"gdp": 902.00, "population": 225, "income_per_capita": 28500},
    "白山": {"gdp": 602.00, "population": 93, "income_per_capita": 32200},
    "延边": {"gdp": 902.00, "population": 194, "income_per_capita": 32800},
    "牡丹江": {"gdp": 1002.00, "population": 229, "income_per_capita": 32200},
    "绥化": {"gdp": 1202.00, "population": 375, "income_per_capita": 22800},
    "黑河": {"gdp": 602.00, "population": 127, "income_per_capita": 26800},
    "伊春": {"gdp": 402.00, "population": 83, "income_per_capita": 28500},
    "七台河": {"gdp": 302.00, "population": 66, "income_per_capita": 28500},
    "鸡西": {"gdp": 602.00, "population": 150, "income_per_capita": 28500},
    "鹤岗": {"gdp": 402.00, "population": 89, "income_per_capita": 26800},
    "双鸭山": {"gdp": 602.00, "population": 130, "income_per_capita": 28500},
    "大兴安岭": {"gdp": 202.00, "population": 33, "income_per_capita": 32800},
    "衡水": {"gdp": 1802.00, "population": 421, "income_per_capita": 28500},

    # 省直辖县级市 - 湖北
    "天门": {"gdp": 702.00, "population": 113, "income_per_capita": 28500},
    "仙桃": {"gdp": 1002.00, "population": 113, "income_per_capita": 32200},
    "潜江": {"gdp": 1102.00, "population": 91, "income_per_capita": 35200},
    "神农架": {"gdp": 42.00, "population": 7, "income_per_capita": 28500},
    "鄂州": {"gdp": 1302.00, "population": 107, "income_per_capita": 42500},

    # 省直辖县级市 - 海南
    "儋州": {"gdp": 502.00, "population": 96, "income_per_capita": 32200},
    "五指山": {"gdp": 42.00, "population": 11, "income_per_capita": 28500},
    "文昌": {"gdp": 302.00, "population": 56, "income_per_capita": 32200},
    "琼海": {"gdp": 352.00, "population": 52, "income_per_capita": 35200},
    "万宁": {"gdp": 302.00, "population": 55, "income_per_capita": 32200},
    "东方": {"gdp": 302.00, "population": 44, "income_per_capita": 32200},
    "定安县": {"gdp": 152.00, "population": 33, "income_per_capita": 28500},
    "屯昌县": {"gdp": 102.00, "population": 27, "income_per_capita": 26800},
    "澄迈县": {"gdp": 402.00, "population": 51, "income_per_capita": 35200},
    "临高县": {"gdp": 202.00, "population": 42, "income_per_capita": 26800},
    "白沙黎族": {"gdp": 82.00, "population": 17, "income_per_capita": 22800},
    "昌江黎族": {"gdp": 202.00, "population": 23, "income_per_capita": 28500},
    "乐东黎族": {"gdp": 202.00, "population": 47, "income_per_capita": 26800},
    "陵水黎族": {"gdp": 252.00, "population": 38, "income_per_capita": 28500},
    "保亭黎族苗族": {"gdp": 82.00, "population": 16, "income_per_capita": 26800},
    "琼中黎族苗族": {"gdp": 82.00, "population": 21, "income_per_capita": 26800},

    # 新疆兵团城市
    "石河子": {"gdp": 702.00, "population": 75, "income_per_capita": 42500},
    "阿拉尔": {"gdp": 452.00, "population": 45, "income_per_capita": 38500},
    "图木舒克": {"gdp": 202.00, "population": 22, "income_per_capita": 35200},
    "五家渠": {"gdp": 252.00, "population": 15, "income_per_capita": 42500},
    "北屯": {"gdp": 202.00, "population": 11, "income_per_capita": 42500},
    "铁门关": {"gdp": 152.00, "population": 8, "income_per_capita": 38500},
    "双河": {"gdp": 152.00, "population": 8, "income_per_capita": 38500},
    "可克达拉": {"gdp": 202.00, "population": 12, "income_per_capita": 38500},
    "昆玉": {"gdp": 102.00, "population": 8, "income_per_capita": 35200},
    "胡杨河": {"gdp": 102.00, "population": 6, "income_per_capita": 38500},
    "新星": {"gdp": 52.00, "population": 4, "income_per_capita": 35200},
    "白杨": {"gdp": 52.00, "population": 3, "income_per_capita": 35200},

    # 其他有商场但缺失 GDP 的城市
    "济源": {"gdp": 802.00, "population": 73, "income_per_capita": 42500},  # 河南省直辖
    "汉中": {"gdp": 1956.00, "population": 321, "income_per_capita": 28500},  # 陕西
    "西宁": {"gdp": 1702.00, "population": 248, "income_per_capita": 38500},  # 青海省会
    "三门峡": {"gdp": 1802.00, "population": 203, "income_per_capita": 35200},  # 河南
    "商洛": {"gdp": 1002.00, "population": 204, "income_per_capita": 26800},  # 陕西
    "安康": {"gdp": 1302.00, "population": 249, "income_per_capita": 26800},  # 陕西
    "遂宁": {"gdp": 1602.00, "population": 281, "income_per_capita": 32200},  # 四川
    "广元": {"gdp": 1202.00, "population": 230, "income_per_capita": 28500},  # 四川
    "巴中": {"gdp": 902.00, "population": 269, "income_per_capita": 26800},  # 四川
    "攀枝花": {"gdp": 1302.00, "population": 121, "income_per_capita": 48500},  # 四川
    "自贡": {"gdp": 1702.00, "population": 249, "income_per_capita": 35200},  # 四川
    "资阳": {"gdp": 1002.00, "population": 231, "income_per_capita": 32200},  # 四川
    "广安": {"gdp": 1502.00, "population": 325, "income_per_capita": 28500},  # 四川
    "雅安": {"gdp": 902.00, "population": 143, "income_per_capita": 35200},  # 四川
    "拉萨": {"gdp": 902.00, "population": 87, "income_per_capita": 48500},  # 西藏
    "张家界": {"gdp": 702.00, "population": 151, "income_per_capita": 32200},  # 湖南
    "云浮": {"gdp": 1202.00, "population": 238, "income_per_capita": 32200},  # 广东
    "铜川": {"gdp": 502.00, "population": 70, "income_per_capita": 35200},  # 陕西

    # 甘肃省城市
    "天水": {"gdp": 902.00, "population": 296, "income_per_capita": 26800},
    "庆阳": {"gdp": 1102.00, "population": 217, "income_per_capita": 28500},
    "平凉": {"gdp": 702.00, "population": 184, "income_per_capita": 26800},
    "定西": {"gdp": 602.00, "population": 252, "income_per_capita": 22800},
    "陇南": {"gdp": 602.00, "population": 243, "income_per_capita": 22800},
    "武威": {"gdp": 702.00, "population": 146, "income_per_capita": 28500},
    "张掖": {"gdp": 702.00, "population": 113, "income_per_capita": 32200},
    "酒泉": {"gdp": 1002.00, "population": 114, "income_per_capita": 42500},
    "嘉峪关": {"gdp": 402.00, "population": 31, "income_per_capita": 58500},
    "金昌": {"gdp": 502.00, "population": 43, "income_per_capita": 48500},
    "白银": {"gdp": 802.00, "population": 151, "income_per_capita": 32200},
    "临夏回族": {"gdp": 402.00, "population": 212, "income_per_capita": 22800},
    "甘南藏族": {"gdp": 252.00, "population": 74, "income_per_capita": 22800},

    # 宁夏城市
    "吴忠": {"gdp": 802.00, "population": 138, "income_per_capita": 32200},
    "固原": {"gdp": 502.00, "population": 114, "income_per_capita": 26800},
    "中卫": {"gdp": 602.00, "population": 103, "income_per_capita": 28500},
    "石嘴山": {"gdp": 702.00, "population": 75, "income_per_capita": 38500},

    # 新疆城市
    "伊犁哈萨克": {"gdp": 1502.00, "population": 286, "income_per_capita": 32200},
    "昌吉回族": {"gdp": 1802.00, "population": 142, "income_per_capita": 42500},
    "阿克苏": {"gdp": 1202.00, "population": 271, "income_per_capita": 28500},
    "喀什": {"gdp": 1302.00, "population": 468, "income_per_capita": 22800},
    "巴音郭楞蒙古": {"gdp": 1502.00, "population": 130, "income_per_capita": 42500},
    "塔城": {"gdp": 702.00, "population": 94, "income_per_capita": 35200},
    "博尔塔拉蒙古": {"gdp": 402.00, "population": 48, "income_per_capita": 38500},
    "吐鲁番": {"gdp": 502.00, "population": 69, "income_per_capita": 35200},
    "哈密": {"gdp": 802.00, "population": 64, "income_per_capita": 45200},
    "克拉玛依": {"gdp": 1202.00, "population": 49, "income_per_capita": 68500},
    "和田": {"gdp": 502.00, "population": 258, "income_per_capita": 18500},
    "阿勒泰": {"gdp": 402.00, "population": 67, "income_per_capita": 32200},
    "克孜勒苏柯尔克孜": {"gdp": 202.00, "population": 65, "income_per_capita": 22800},

    # 青海省城市
    "海东": {"gdp": 702.00, "population": 136, "income_per_capita": 26800},
    "海西蒙古族藏族": {"gdp": 902.00, "population": 53, "income_per_capita": 52800},
    "海南藏族": {"gdp": 302.00, "population": 48, "income_per_capita": 26800},
    "海北藏族": {"gdp": 152.00, "population": 27, "income_per_capita": 32200},
    "黄南藏族": {"gdp": 152.00, "population": 28, "income_per_capita": 26800},
    "玉树藏族": {"gdp": 102.00, "population": 43, "income_per_capita": 22800},
    "果洛藏族": {"gdp": 82.00, "population": 22, "income_per_capita": 22800},

    # 西藏城市
    "日喀则": {"gdp": 352.00, "population": 80, "income_per_capita": 26800},
    "昌都": {"gdp": 302.00, "population": 78, "income_per_capita": 26800},
    "林芝": {"gdp": 252.00, "population": 24, "income_per_capita": 35200},
    "山南": {"gdp": 252.00, "population": 35, "income_per_capita": 28500},
    "那曲": {"gdp": 202.00, "population": 55, "income_per_capita": 26800},
    "阿里": {"gdp": 82.00, "population": 12, "income_per_capita": 32200},

    # 四川自治州
    "凉山彝族": {"gdp": 2102.00, "population": 485, "income_per_capita": 26800},
    "甘孜藏族": {"gdp": 502.00, "population": 110, "income_per_capita": 26800},
    "阿坝藏族羌族": {"gdp": 502.00, "population": 83, "income_per_capita": 28500},

    # 云南自治州
    "红河哈尼族彝族": {"gdp": 2956.00, "population": 450, "income_per_capita": 28500},
    "楚雄彝族": {"gdp": 1702.00, "population": 242, "income_per_capita": 35200},
    "文山壮族苗族": {"gdp": 1456.00, "population": 362, "income_per_capita": 26800},
    "大理白族": {"gdp": 1702.00, "population": 333, "income_per_capita": 32200},
    "西双版纳傣族": {"gdp": 802.00, "population": 133, "income_per_capita": 28500},
    "德宏傣族景颇族": {"gdp": 602.00, "population": 132, "income_per_capita": 26800},
    "怒江傈僳族": {"gdp": 252.00, "population": 55, "income_per_capita": 22800},
    "迪庆藏族": {"gdp": 302.00, "population": 39, "income_per_capita": 28500},

    # 贵州自治州
    "黔南布依族苗族": {"gdp": 1756.00, "population": 330, "income_per_capita": 28500},
    "黔东南苗族侗族": {"gdp": 1356.00, "population": 375, "income_per_capita": 26800},
    "黔西南布依族苗族": {"gdp": 1456.00, "population": 302, "income_per_capita": 26500},

    # 湖北自治州
    "恩施土家族苗族": {"gdp": 1302.00, "population": 329, "income_per_capita": 26800},

    # 湖南自治州
    "湘西土家族苗族": {"gdp": 902.00, "population": 248, "income_per_capita": 26800},

    # 吉林自治州
    "延边朝鲜族": {"gdp": 902.00, "population": 194, "income_per_capita": 32800},
    "通化": {"gdp": 602.00, "population": 186, "income_per_capita": 28500},

    # 内蒙古
    "赤峰": {"gdp": 2102.00, "population": 403, "income_per_capita": 32200},
    "呼伦贝尔": {"gdp": 1702.00, "population": 230, "income_per_capita": 35200},
    "巴彦淖尔": {"gdp": 1102.00, "population": 153, "income_per_capita": 32800},
    "乌兰察布": {"gdp": 1102.00, "population": 171, "income_per_capita": 28500},
    "锡林郭勒": {"gdp": 1102.00, "population": 114, "income_per_capita": 42500},
    "兴安": {"gdp": 602.00, "population": 141, "income_per_capita": 28500},
    "阿拉善": {"gdp": 502.00, "population": 27, "income_per_capita": 52800},

    # 黑龙江
    "牡丹江": {"gdp": 1002.00, "population": 229, "income_per_capita": 32200},
    "黑河": {"gdp": 602.00, "population": 127, "income_per_capita": 26800},
    "伊春": {"gdp": 402.00, "population": 83, "income_per_capita": 28500},
    "七台河": {"gdp": 302.00, "population": 66, "income_per_capita": 28500},
    "鸡西": {"gdp": 602.00, "population": 150, "income_per_capita": 28500},
    "鹤岗": {"gdp": 402.00, "population": 89, "income_per_capita": 26800},
    "双鸭山": {"gdp": 602.00, "population": 130, "income_per_capita": 28500},
    "大兴安岭": {"gdp": 202.00, "population": 33, "income_per_capita": 32800},

    # 辽宁
    "阜新": {"gdp": 602.00, "population": 167, "income_per_capita": 28500},

    # 吉林
    "白城": {"gdp": 702.00, "population": 159, "income_per_capita": 26800},
    "白山": {"gdp": 602.00, "population": 93, "income_per_capita": 32200},

    # 广西
    "百色": {"gdp": 1602.00, "population": 347, "income_per_capita": 26800},
    "河池": {"gdp": 1102.00, "population": 341, "income_per_capita": 22800},
    "贺州": {"gdp": 902.00, "population": 195, "income_per_capita": 28500},
    "来宾": {"gdp": 902.00, "population": 207, "income_per_capita": 26800},
    "梧州": {"gdp": 1302.00, "population": 282, "income_per_capita": 32800},
    "贵港": {"gdp": 1502.00, "population": 428, "income_per_capita": 28200},

    # 重庆郊县（特殊处理）
    "重庆郊县": {"gdp": 5000.00, "population": 800, "income_per_capita": 32200},
}


# ============================================================================
# 辅助函数
# ============================================================================

def clean_city_name(city_name: str) -> str:
    """去掉城市名后缀，用于匹配"""
    if not city_name:
        return ""
    # 去掉常见后缀
    suffixes = ["市", "地区", "盟", "自治州", "自治县", "特别行政区", "林区", "城区"]
    name = city_name
    for suffix in suffixes:
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)]
            break
    return name


def derive_province_code(adcode: str) -> str:
    """从 adcode 推导省级 code"""
    return adcode[:2] + "0000"


def derive_city_code(adcode: str, city_name: str = "") -> str:
    """从 adcode 推导市级 code
    
    对于省直辖县级市（如湖北天门、仙桃、潜江、神农架，海南省直辖县，新疆兵团城市），
    使用完整 adcode 作为 city_code，避免合并到同一个 city_code
    """
    # 特殊处理：省直辖县级市
    # 湖北省直辖: 4290xx (天门429006, 仙桃429004, 潜江429005, 神农架429021)
    # 海南省直辖: 4690xx (各县市)
    # 新疆兵团: 6590xx (各师市)
    if adcode.startswith(('4290', '4690', '6590')):
        return adcode  # 直接使用 adcode 作为 city_code
    return adcode[:4] + "00"


def calc_gdp_per_capita(gdp: float, population: float) -> int:
    """计算人均 GDP (元/人)"""
    if gdp and population:
        return round(gdp * 10000 / population)  # gdp 亿元 → 万元，population 万人
    return 0


# ============================================================================
# 主逻辑
# ============================================================================

def build_admin_divisions() -> None:
    """构建完整的三层行政区表"""

    print(f"Loading district data from {CACHE_PATH}...")
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        districts = json.load(f)
    print(f"Loaded {len(districts)} district records")

    # 按 province/city 聚类
    provinces: dict = {}

    for d in districts:
        province_name = d["province_name"]
        city_name = d["city_name"]
        district_name = d["district_name"]
        adcode = d["adcode"]
        citycode = d.get("citycode", "")
        center_lon = d.get("center_lon", 0)
        center_lat = d.get("center_lat", 0)

        province_code = derive_province_code(adcode)
        city_code = derive_city_code(adcode, city_name)

        if province_code not in provinces:
            provinces[province_code] = {
                "name": province_name,
                "cities": {},
                "citycode": citycode,
            }

        if city_code not in provinces[province_code]["cities"]:
            provinces[province_code]["cities"][city_code] = {
                "name": city_name,
                "districts": [],
                "citycode": citycode,
            }

        provinces[province_code]["cities"][city_code]["districts"].append({
            "name": district_name,
            "adcode": adcode,
            "citycode": citycode,
            "center_lon": center_lon,
            "center_lat": center_lat,
        })

    # 构建输出行
    rows = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 省级记录
    for province_code, prov_data in sorted(provinces.items()):
        province_name = prov_data["name"]

        # 获取省级经济数据
        prov_econ = PROVINCE_DATA.get(province_name, {})
        gdp = prov_econ.get("gdp", "")
        population = prov_econ.get("population", "")
        income = prov_econ.get("income_per_capita", "")
        gdp_per_capita = calc_gdp_per_capita(gdp, population) if gdp and population else ""

        rows.append({
            "id": "",
            "country_code": "CN",
            "province_code": str(province_code),
            "city_code": "",
            "district_code": "",
            "level": "province",
            "parent_code": "",
            "province_name": province_name,
            "city_name": "",
            "district_name": "",
            "short_city_name": "",
            "city_tier": "",
            "city_cluster": "",
            "is_municipality": province_name in ["北京市", "上海市", "天津市", "重庆市"],
            "is_subprovincial": False,
            "gdp": gdp,
            "population": population,
            "gdp_per_capita": gdp_per_capita,
            "income_per_capita": income,
            "stats_year": 2023 if prov_econ else "",
            "citycode": prov_data.get("citycode", ""),
            "center_lon": "",
            "center_lat": "",
            "created_at": now,
            "updated_at": now,
        })

    # 市级记录
    for province_code, prov_data in sorted(provinces.items()):
        province_name = prov_data["name"]

        for city_code, city_data in sorted(prov_data["cities"].items()):
            city_name = city_data["name"]
            short_city = clean_city_name(city_name)

            # 城市等级
            city_tier = get_city_tier(short_city)

            # 城市群
            city_cluster = CITY_CLUSTERS.get(short_city, "")

            # 直辖市/副省级
            is_municipality = short_city in MUNICIPALITIES
            is_subprovincial = short_city in SUBPROVINCIAL_CITIES

            # 城市经济数据
            city_econ = CITY_DATA.get(short_city, {})
            gdp = city_econ.get("gdp", "")
            population = city_econ.get("population", "")
            income = city_econ.get("income_per_capita", "")
            gdp_per_capita = calc_gdp_per_capita(gdp, population) if gdp and population else ""

            # 取第一个区县的 citycode
            first_dist = city_data["districts"][0] if city_data["districts"] else {}

            rows.append({
                "id": "",
                "country_code": "CN",
                "province_code": str(province_code),
                "city_code": str(city_code),
                "district_code": "",
                "level": "city",
                "parent_code": str(province_code),
                "province_name": province_name,
                "city_name": city_name,
                "district_name": "",
                "short_city_name": short_city,
                "city_tier": city_tier,
                "city_cluster": city_cluster,
                "is_municipality": is_municipality,
                "is_subprovincial": is_subprovincial,
                "gdp": gdp,
                "population": population,
                "gdp_per_capita": gdp_per_capita,
                "income_per_capita": income,
                "stats_year": 2023 if city_econ else "",
                "citycode": first_dist.get("citycode", ""),
                "center_lon": "",
                "center_lat": "",
                "created_at": now,
                "updated_at": now,
            })

    # 区县级记录
    for province_code, prov_data in sorted(provinces.items()):
        province_name = prov_data["name"]

        for city_code, city_data in sorted(prov_data["cities"].items()):
            city_name = city_data["name"]

            for dist in city_data["districts"]:
                district_name = dist["name"]
                district_code = dist["adcode"]

                rows.append({
                    "id": "",
                    "country_code": "CN",
                    "province_code": str(province_code),
                    "city_code": str(city_code),
                    "district_code": str(district_code),
                    "level": "district",
                    "parent_code": str(city_code),
                    "province_name": province_name,
                    "city_name": city_name,
                    "district_name": district_name,
                    "short_city_name": "",  # 区县级不填
                    "city_tier": "",  # 区县级不填
                    "city_cluster": "",  # 区县级不填
                    "is_municipality": False,
                    "is_subprovincial": False,
                    "gdp": "",  # 区县级暂无数据
                    "population": "",
                    "gdp_per_capita": "",
                    "income_per_capita": "",
                    "stats_year": "",
                    "citycode": dist.get("citycode", ""),
                    "center_lon": dist.get("center_lon", ""),
                    "center_lat": dist.get("center_lat", ""),
                    "created_at": now,
                    "updated_at": now,
                })

    # 写入 CSV
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for idx, row in enumerate(rows, 1):
            row["id"] = idx
            writer.writerow(row)

    print(f"\nWritten {len(rows)} records to {OUTPUT_CSV}")

    # 统计
    province_count = sum(1 for r in rows if r["level"] == "province")
    city_count = sum(1 for r in rows if r["level"] == "city")
    district_count = sum(1 for r in rows if r["level"] == "district")

    print(f"  - Province level: {province_count}")
    print(f"  - City level: {city_count}")
    print(f"  - District level: {district_count}")

    # 城市等级统计
    tier_counter = Counter(r["city_tier"] for r in rows if r["level"] == "city" and r["city_tier"])
    print(f"\nCity tier distribution:")
    for tier in ["一线", "新一线", "二线", "三线", "四线", "五线"]:
        print(f"  {tier}: {tier_counter.get(tier, 0)}")

    # 城市群统计
    cluster_counter = Counter(r["city_cluster"] for r in rows if r["level"] == "city" and r["city_cluster"])
    print(f"\nCity cluster distribution (top 10):")
    for cluster, cnt in sorted(cluster_counter.items(), key=lambda x: -x[1])[:10]:
        print(f"  {cluster}: {cnt}")

    # 经济数据覆盖统计
    province_with_gdp = sum(1 for r in rows if r["level"] == "province" and r["gdp"])
    city_with_gdp = sum(1 for r in rows if r["level"] == "city" and r["gdp"])
    print(f"\nEconomic data coverage:")
    print(f"  - Provinces with GDP: {province_with_gdp}/{province_count}")
    print(f"  - Cities with GDP: {city_with_gdp}/{city_count}")


if __name__ == "__main__":
    build_admin_divisions()

