import os
from dotenv import load_dotenv

load_dotenv("E:/1-workspace/Google/Antigravity/edcat_v2/.env")
import sys
sys.path.insert(0, "E:/1-workspace/Google/Antigravity/edcat_v2")

from edcat_root.rag_agent.agent import RagAgent

agent = RagAgent(safe_mode=False)
res = agent.invoke({"messages": [("user", "O que o texto diz sobre arquétipos?")]})
print("RESPOSTA:", res)
