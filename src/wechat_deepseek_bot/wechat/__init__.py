"""Transport contracts only; no platform client integration is distributed."""

from .factory import OfficialAdapterRequired, create_wechat_transport

__all__ = ["OfficialAdapterRequired", "create_wechat_transport"]
