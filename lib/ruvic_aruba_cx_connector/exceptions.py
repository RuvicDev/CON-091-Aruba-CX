"""Excepciones propias del conector Aruba CX.

Separan los tres tipos de fallo que el usuario debe distinguir:
autenticación, red/servidor y datos. Nunca exponemos excepciones
crípticas del cliente HTTP subyacente.
"""


class ArubaCxConnectorError(Exception):
    """Error base del conector."""


class ArubaCxAuthError(ArubaCxConnectorError):
    """Credenciales inválidas o permisos insuficientes."""


class ArubaCxNetworkError(ArubaCxConnectorError):
    """No se pudo alcanzar el servicio (red, timeout o error del servidor)."""


class ArubaCxDataError(ArubaCxConnectorError):
    """La operación es válida pero los datos o parámetros no lo son."""
