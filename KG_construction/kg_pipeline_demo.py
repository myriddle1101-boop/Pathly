import os
from openai import OpenAI

from env_loader import load_project_env

load_project_env()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "只回复：API OK"}],
    temperature=0
)
print(resp.choices[0].message.content)
