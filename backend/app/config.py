import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(os.environ.get("YUNYUN_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    llm_provider: Literal["bailian", "mock"] = "bailian"
    dashscope_api_key: SecretStr = SecretStr("")
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.8-max"
    yunyun_mode: Literal["pc", "web"] = "web"
    yunyun_data_dir: Path = PROJECT_ROOT / ".runtime"
    yunyun_workspace: Path | None = None
    yunyun_local_token: SecretStr = SecretStr("")
    yunyun_hosts: str = "localhost,127.0.0.1,testserver"
    yunyun_secure_cookie: bool = False
    max_steps: int = Field(default=12, ge=1, le=12)
    max_tools: int = Field(default=24, ge=1, le=24)
    max_active_seconds: float = Field(default=720, gt=0, le=720)
    model_timeout_seconds: float = Field(default=60, gt=0, le=60)
    max_output_tokens: int = Field(default=4096, ge=1, le=4096)
    max_input_tokens: int = Field(default=80000, ge=1, le=80000)
    max_total_output_tokens: int = Field(default=12000, ge=1, le=12000)
    max_run_cny: float = Field(default=3, gt=0, le=3)
    max_project_cny: float = Field(default=45, gt=0, le=45)
    max_session_cny: float = Field(default=9, gt=0, le=45)
    # 更换模型必须显式核对价格；不能沿用旗舰价格冒充精确账单。
    llm_input_cny_per_million: float | None = Field(default=None, gt=0)
    llm_output_cny_per_million: float | None = Field(default=None, gt=0)

    def prices(self) -> tuple[float, float]:
        if self.llm_provider == "mock":
            return 0, 0
        if self.llm_input_cny_per_million and self.llm_output_cny_per_million:
            return self.llm_input_cny_per_million, self.llm_output_cny_per_million
        if self.llm_model == "qwen3.8-max":
            return 12, 36
        from app.domain import AppError

        raise AppError("PRICE_UNKNOWN", "新模型需先配置经核对的输入、输出价格。", 503)
