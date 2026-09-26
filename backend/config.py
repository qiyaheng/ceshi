"""全局配置：所有密钥只从环境变量 / .env 读取，禁止硬编码。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "FinResearcher Agent"
    version: str = "0.1.0"

    # 本服务对外鉴权 Key，留空不鉴权
    service_api_key: str = ""

    # 主力：火山方舟
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = "doubao-seed-2.0-mini"

    # 备份：DeepSeek 官方
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # 自定义模型：任何 OpenAI 兼容端点（本地/自建均可），填地址+模型名即可，Key 可留空
    custom_model: str = ""
    custom_base_url: str = ""
    custom_api_key: str = "none"

    # 本地小模型（CPU 推理）较慢，默认给足 300 秒；云端渠道可改小
    llm_timeout: int = 300

    def has_any_llm_key(self) -> bool:
        return bool(
            self.ark_api_key
            or self.deepseek_api_key
            or (self.custom_model and self.custom_base_url)
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
