import os
from openai import OpenAI

api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("VITE_BAILIAN_API_KEY")
base_url = os.getenv("BAILIAN_BASE_URL") or os.getenv("VITE_BAILIAN_BASE_URL") \
    or "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = os.getenv("VITE_BAILIAN_MODEL") or "qwen-plus"

if not api_key:
    raise RuntimeError("请先设置 DASHSCOPE_API_KEY 或 VITE_BAILIAN_API_KEY")

client = OpenAI(api_key=api_key, base_url=base_url)

resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "你是谁？"}],
    # 关闭“思考模式”，只返回直接回答
    # 对于 deepseek-v3.2-exp，如果不传 extra_body 或设为 False，即为普通模式
    extra_body={"enable_thinking": False},
)

content = resp.choices[0].message.content
print("\n=== 模型回复 ===\n", content)
print("\n=== Token 统计 ===")
print(resp.usage)
