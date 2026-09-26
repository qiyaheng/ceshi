"""模型适配层：基于 LiteLLM Router 统一多家国产渠道。

渠道优先级：火山方舟(主) -> DeepSeek(备) -> 自定义端点(兜底，可为本地免密钥服务)
- 任一渠道超时/报错/限流，Router 自动 failover 到下一个渠道
- 未来接入自有精调模型时，只需在此处增改一个 model_list 条目，
  Agent 与对外 API 均无感知
"""
import os
from typing import Any, Optional

# 国内网络访问 GitHub 不稳定，强制使用 LiteLLM 内置本地价格表，避免启动时长时间超时
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
# 本机常见代理环境变量会劫持 localhost 请求导致 502，强制本地回环地址直连
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

import litellm
from litellm import Router

from ..config import get_settings

litellm.suppress_debug_info = True
litellm.modify_params = True  # 渠道不支持的参数自动裁剪，提升跨渠道兼容性


def _build_router() -> Optional[Router]:
    s = get_settings()

    # (逻辑名, 模型, base_url, api_key) —— 按优先级排列
    candidates: list[tuple[str, str, str, str]] = []
    if s.ark_api_key:
        candidates.append(("primary", s.ark_model, s.ark_base_url, s.ark_api_key))
    if s.deepseek_api_key:
        candidates.append(
            ("backup", s.deepseek_model, s.deepseek_base_url, s.deepseek_api_key)
        )
    if s.custom_model and s.custom_base_url:
        # 自定义 OpenAI 兼容端点（本地服务如 Ollama/LM Studio/vLLM 均可），Key 可留空
        candidates.append(
            ("fallback", s.custom_model, s.custom_base_url, s.custom_api_key)
        )
    if not candidates:
        return None

    global default_model
    default_model = candidates[0][0]  # 首个可用渠道作为默认入口

    model_list = [
        {
            "model_name": logical_name,
            "litellm_params": {
                # openai/ 前缀：以上渠道全部兼容 OpenAI Chat Completions 协议
                "model": f"openai/{model}",
                "api_base": base_url,
                "api_key": api_key,
                "timeout": s.llm_timeout,
            },
        }
        for logical_name, model, base_url, api_key in candidates
    ]

    # 依次降级：primary -> backup -> fallback
    names = [c[0] for c in candidates]
    fallbacks = [{names[i]: names[i + 1:]} for i in range(len(names) - 1)]

    return Router(
        model_list=model_list,
        fallbacks=fallbacks,
        num_retries=1,
        allowed_fails=1,          # 快速触发降级，避免长时间等待
        enable_pre_call_checks=False,
    )


default_model = "primary"
router = _build_router()


async def chat(
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    temperature: float = 0.3,
) -> Any:
    """统一对话入口。请求首个可用渠道，故障由 Router 自动降级。"""
    if router is None:
        raise RuntimeError(
            "未配置任何模型渠道，请复制 .env.example 为 .env 并填写 ARK_API_KEY 或 CUSTOM_* 等"
        )
    kwargs: dict[str, Any] = {"temperature": temperature}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return await router.acompletion(model=default_model, messages=messages, **kwargs)
