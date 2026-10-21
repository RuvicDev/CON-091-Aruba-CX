"""Consulta de switches HPE Aruba CX (AOS-CX REST API): información del switch, interfaces, VLANs y estado de puertos. Solo lectura"""

from .client import ArubaCxClient
from .config import ENV_PREFIX, ArubaCxConfig
from .exceptions import (
    ArubaCxAuthError,
    ArubaCxConnectorError,
    ArubaCxDataError,
    ArubaCxNetworkError,
)
from .logging_utils import setup_logging

__all__ = [
    "ArubaCxAuthError",
    "ArubaCxClient",
    "ArubaCxConfig",
    "ArubaCxConnectorError",
    "ArubaCxDataError",
    "ArubaCxNetworkError",
    "ENV_PREFIX",
    "setup_logging",
]

__version__ = "1.0.0"
