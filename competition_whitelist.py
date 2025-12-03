"""存放“排他但没有报店/开店”且业务已确认合理的商场白名单。

这些 mall 会在竞争字段检查中被忽略，不再提示风险。
"""

from __future__ import annotations

# mall_id 列表：dji_exclusive=1 但 dji_opened/dji_reported 都为 0，
# 且业务确认“只是签了 PT，但还没正式报店/开店”，属于正常情况。
WHITELIST_EXCLUSIVE_MALL_IDS = {
    "MALL_00556",  # 徐州彭城苏宁广场
    "MALL_00657",  # 绍兴银泰
    "MALL_00737",  # 深圳大运天地
    "MALL_00742",  # 龙湖北京长楹天街
    "MALL_00743",  # 西三旗万象汇
    "MALL_00744",  # 昆明瑞鼎城悦容匯购物公园A馆
    "MALL_00746",  # 港惠购物中心
    "MALL_00747",  # 吾悦广场(兰州安宁店)
}

