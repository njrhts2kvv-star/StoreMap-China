"""使用 LLM 修复 Mall_Master_Cleaned.csv 中明显错误的 mall_name

问题：有些 mall_name 实际上是商场内的店铺名称（如屈臣氏、美宜佳等），
而不是商场本身的名称。

解决方案：
1. 找出 mall_name 和 original_name 不同的记录
2. 使用 LLM 判断 mall_name 是否是一个有效的商场名称
3. 如果不是，则使用 original_name 替换
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent
MALL_CSV = BASE_DIR / "Mall_Master_Cleaned.csv"
MALL_CSV_BACKUP = BASE_DIR / "Mall_Master_Cleaned.csv.backup"

# LLM 配置
LLM_BASE_URL = os.getenv("BAILIAN_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_KEY: Optional[str] = None


def load_llm_key() -> Optional[str]:
    """从环境变量或.env.local文件加载 LLM API Key"""
    key = os.getenv("BAILIAN_API_KEY")
    if key:
        return key

    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return None

    parsed: dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "BAILIAN_API_KEY" and v.strip():
                return v.strip().strip("'\"")
    return None


LLM_KEY = load_llm_key()


def check_mall_name_with_llm(mall_name: str, original_name: str) -> dict:
    """使用 LLM 判断 mall_name 是否是有效的商场名称
    
    返回:
        {
            "is_valid_mall": bool,  # mall_name 是否是有效商场名
            "recommended_name": str,  # 推荐使用的名称
            "reason": str  # 判断理由
        }
    """
    if not LLM_KEY:
        print("[警告] 未配置 BAILIAN_API_KEY，跳过 LLM 判断")
        return {"is_valid_mall": True, "recommended_name": mall_name, "reason": "未配置LLM"}
    
    url = LLM_BASE_URL.rstrip('/') + '/chat/completions'
    
    prompt = f"""你是一个商场名称验证专家。请判断以下名称是否是一个有效的"商场/购物中心"名称。

当前名称: {mall_name}
原始名称: {original_name}

判断标准:
1. 有效的商场名称通常包含：万达广场、购物中心、百货、商场、广场、城、汇、天街、大悦城、银泰、万象城、华润、龙湖等关键词
2. 无效的商场名称通常是商场内的店铺，如：屈臣氏、美宜佳、盒马鲜生、Ole超市、沃尔玛、星巴克、肯德基等品牌连锁店
3. 如果当前名称像是"店铺(商场店)"的格式，说明当前名称是店铺而非商场

请以JSON格式回复:
{{
    "is_valid_mall": true/false,
    "recommended_name": "推荐使用的商场名称",
    "reason": "简短说明判断理由"
}}

注意:
- 如果 mall_name 是有效商场名，recommended_name 就用 mall_name
- 如果 mall_name 是店铺名，recommended_name 应该用 original_name 或从 mall_name 中提取出的商场名
- 只返回JSON，不要其他内容"""

    try:
        resp = requests.post(
            url,
            json={
                "model": "qwen-plus",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {LLM_KEY}",
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        
        # 解析 JSON
        # 处理可能的 markdown 代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        result = json.loads(content)
        return result
        
    except Exception as e:
        print(f"[LLM错误] {e}")
        return {"is_valid_mall": True, "recommended_name": mall_name, "reason": f"LLM调用失败: {e}"}


def main():
    print("=" * 60)
    print("使用 LLM 修复商场名称")
    print("=" * 60)
    
    if not LLM_KEY:
        print("\n[错误] 未找到 BAILIAN_API_KEY")
        print("请在 .env.local 文件中配置 BAILIAN_API_KEY")
        return
    
    # 读取商场数据
    df = pd.read_csv(MALL_CSV)
    print(f"\n[信息] 读取商场数据: {len(df)} 条记录")
    
    # 备份原文件
    df.to_csv(MALL_CSV_BACKUP, index=False)
    print(f"[信息] 已备份到: {MALL_CSV_BACKUP}")
    
    # 找出 mall_name 和 original_name 不同的记录
    different_names = df[df['mall_name'] != df['original_name']].copy()
    print(f"\n[信息] mall_name 和 original_name 不同的记录: {len(different_names)} 条")
    
    if len(different_names) == 0:
        print("[完成] 没有需要检查的记录")
        return
    
    # 用于统计
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    # 批量处理
    print("\n[处理] 开始 LLM 验证...\n")
    
    for idx, row in different_names.iterrows():
        mall_id = row['mall_id']
        mall_name = row['mall_name']
        original_name = row['original_name']
        
        print(f"[{idx}] 检查: {mall_name}")
        print(f"       原始: {original_name}")
        
        # 调用 LLM
        result = check_mall_name_with_llm(mall_name, original_name)
        
        if result["is_valid_mall"]:
            print(f"       ✓ 有效商场名称")
            skipped_count += 1
        else:
            recommended = result["recommended_name"]
            reason = result["reason"]
            print(f"       ✗ 无效: {reason}")
            print(f"       → 修正为: {recommended}")
            
            # 更新 DataFrame
            df.loc[df['mall_id'] == mall_id, 'mall_name'] = recommended
            fixed_count += 1
        
        print()
        
        # 限速
        time.sleep(0.5)
    
    # 保存结果
    df.to_csv(MALL_CSV, index=False)
    
    print("=" * 60)
    print(f"[完成] 处理结果:")
    print(f"  - 检查总数: {len(different_names)}")
    print(f"  - 已修正: {fixed_count}")
    print(f"  - 保持不变: {skipped_count}")
    print(f"  - 错误: {error_count}")
    print(f"\n[完成] 已保存: {MALL_CSV}")


if __name__ == "__main__":
    main()

