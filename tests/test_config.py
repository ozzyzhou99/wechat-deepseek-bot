import pytest

from wechat_deepseek_bot.config import ConfigError, load_config


def valid_env(**overrides):
    env = {"DEEPSEEK_API_KEY": "test-key"}
    env.update(overrides)
    return env


def test_safe_defaults_disable_archiving():
    config = load_config(valid_env())
    assert config.chat_archive_enabled is False
    assert config.chat_archive_retention_days == 1
    assert config.app_timezone == "Asia/Shanghai"
    assert config.chat_archive_max_summary_messages == 1000


def test_missing_api_key_is_clear():
    with pytest.raises(ConfigError, match="DEEPSEEK_API_KEY"):
        load_config(valid_env(DEEPSEEK_API_KEY=""))


def test_configuration_validation():
    assert load_config(valid_env(REPLY_ONLY_WHEN_AT="false")).reply_only_when_at is False
    assert load_config(valid_env(POLITICS_FILTER_MODE="keywords")).politics_filter_mode == "keywords"
    with pytest.raises(ConfigError, match="SARCASM_LEVEL"):
        load_config(valid_env(SARCASM_LEVEL="4"))
    with pytest.raises(ConfigError, match="POLITICS_FILTER_MODE"):
        load_config(valid_env(POLITICS_FILTER_MODE="unsafe"))
