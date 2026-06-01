"""Project configuration loaded from .env or Streamlit Cloud secrets."""

import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)


def _get_setting(name: str, default: str = "") -> str:
    """Read config from environment first, then Streamlit secrets."""
    value = os.getenv(name)
    if value is not None:
        return str(value).strip()

    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()
        for section_name in ("deepseek", "supabase", "app"):
            section = st.secrets.get(section_name, {})
            try:
                if name in section:
                    return str(section[name]).strip()
            except TypeError:
                pass
    except Exception:
        pass

    return default


def disable_proxy():
    """关闭系统代理，避免 API 调用被本地代理影响
    
    做两件事：
    1. 清除代理相关环境变量
    2. 设置 NO_PROXY='*' 绕过 Windows 系统级代理（注册表/IE设置）
       httpx/openai 底层会自动读取系统代理，仅清环境变量不够
    """
    for key in [
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ]:
        os.environ.pop(key, None)
    # 关键：设置 NO_PROXY='*' 让 httpx/openai 跳过所有系统代理
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


# 启动时默认关闭代理
disable_proxy()

# --- LLM provider configuration ---

# DeepSeek official OpenAI-compatible API configuration.
DEEPSEEK_API_KEY: str = _get_setting("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL: str = _get_setting("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# DeepSeek V3 non-thinking chat model name in the official OpenAI-compatible API.
MODEL_NAME: str = _get_setting("MODEL_NAME", "deepseek-chat")
MAX_ROUNDS: int = int(_get_setting("MAX_ROUNDS", "8"))
MIN_FOLLOWUP_ROUNDS: int = int(_get_setting("MIN_FOLLOWUP_ROUNDS", "5"))
TEMPERATURE: float = float(_get_setting("TEMPERATURE", "0.2"))

# Optional Supabase output archive configuration.
SUPABASE_URL: str = _get_setting("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY: str = _get_setting("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY: str = _get_setting("SUPABASE_ANON_KEY")
SUPABASE_OUTPUTS_TABLE: str = _get_setting("SUPABASE_OUTPUTS_TABLE", "output_files")

# 风险等级阈值
RISK_LOW_THRESHOLD: int = 30
RISK_HIGH_THRESHOLD: int = 60

# 谎言指数权重
WEIGHT_SEMANTIC: float = 0.30           # 语义一致性权重
WEIGHT_LOGICAL: float = 0.25            # 逻辑一致性权重
WEIGHT_DOMAIN: float = 0.20             # 领域一致性权重
WEIGHT_PSYCHO_LINGUISTIC: float = 0.15  # 心理语言学权重
WEIGHT_UNRESOLVED_FOLLOWUP: float = 0.10  # 未解决追问权重

UNRESOLVED_FOLLOWUP_PER_SCORE: int = 20    # 未解决追问每项扣分：每个未解决的追问按此分值计入谎言指数

# ---- v3 新增：路由配置 ----
# 是否启用按需专家调用
ENABLE_ON_DEMAND_SPECIALISTS: bool = True

# 低风险阈值：低于此值不调用专家
LOW_RISK_SKIP_THRESHOLD: int = 30

# 中风险阈值：低于此值只调用1个专家
MEDIUM_RISK_THRESHOLD: int = 50

# 高风险阈值：高于此值调用多个或全部专家
HIGH_RISK_THRESHOLD: int = 70


