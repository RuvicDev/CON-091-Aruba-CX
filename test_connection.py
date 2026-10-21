"""Prueba de conexión estándar del conector aruba_cx.

Firma estándar Ruvic: def test_connection() -> tuple[bool, str]
- Lee la configuración EXCLUSIVAMENTE de las env vars RUVIC_ARUBA_CX_*.
- Nunca lanza excepciones; retorna (ok, mensaje).

Ejecutable también como script para pruebas locales:
    python test_connection.py
"""

from __future__ import annotations


def test_connection() -> tuple[bool, str]:
    """Inicia y cierra sesión en el switch AOS-CX consultando su hostname con las env vars RUVIC_ARUBA_CX_*."""
    try:
        from ruvic_aruba_cx_connector import (
            ArubaCxAuthError,
            ArubaCxClient,
            ArubaCxDataError,
            ArubaCxNetworkError,
        )
    except ImportError:
        return (
            False,
            (
                "La librería ruvic-aruba-cx-connector no está instalada. "
                "Instala con: pip install git+https://github.com/RuvicDev/"
                "CON-091-Aruba-CX.git#subdirectory=lib"
            ),
        )

    try:
        client = ArubaCxClient()  # valida que existan las env vars
    except ValueError as exc:
        return False, str(exc)

    try:
        client.ping()
    except ArubaCxAuthError as exc:
        return False, f"Autenticación fallida: {exc}"
    except ArubaCxNetworkError as exc:
        return False, f"Error de red: {exc}"
    except ArubaCxDataError as exc:
        return False, f"Error de datos: {exc}"
    except Exception as exc:  # noqa: BLE001 - red de seguridad: jamás propagar
        return False, f"Error inesperado: {exc}"

    return True, f"Conexión exitosa al switch Aruba CX ({client.config.host})"


if __name__ == "__main__":
    ok, message = test_connection()
    print(f"{'OK' if ok else 'FALLO'}: {message}")
    raise SystemExit(0 if ok else 1)
