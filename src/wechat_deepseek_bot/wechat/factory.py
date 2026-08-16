"""Safe transport boundary for the public framework."""

from __future__ import annotations


class OfficialAdapterRequired(RuntimeError):
    """Raised when no platform-authorized adapter has been supplied."""


def create_wechat_transport(config, engine, logger):
    """Refuse to create a client integration in the public distribution."""

    del config, engine, logger
    raise OfficialAdapterRequired(
        "This public framework includes no WeChat client adapter. Connect an official "
        "or explicitly authorized platform API in a separate private integration."
    )
