"""配置管理:用 pydantic-settings 从 .env 读取,自带类型校验。

复用第一阶段学的 BaseSettings。env_file 用绝对路径锚定到本文件所在目录,
这样从任何工作目录运行都能找到 .env(避免之前踩过的相对路径坑)。
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
    )

    # 大模型 API 配置。国内厂商多兼容 OpenAI 接口,改 base_url + model 即可切换。
    api_key: str
    base_url: str
    model: str


settings = Settings()
