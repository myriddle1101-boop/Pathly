import os
from openai import OpenAI

from env_loader import load_project_env


load_project_env()


def test_openai_api():
    """测试 OpenAI API 连通性"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        print("正在测试 OpenAI API...")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "只回复：API OK"}],
            temperature=0
        )
        
        result = resp.choices[0].message.content
        print(f"\n✅ API 测试成功！响应：{result}")
        return True
    except Exception as e:
        print(f"\n❌ API 测试失败：{e}")
        return False


if __name__ == "__main__":
    test_openai_api()
