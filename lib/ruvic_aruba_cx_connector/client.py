"""Cliente de solo lectura para switches HPE Aruba CX (AOS-CX REST API).

Capacidades:
- get_switch_info():  hostname, plataforma, firmware, número de serie, hora de arranque.
- list_interfaces():  interfaces con estado administrativo, de enlace y velocidad.
- list_vlans():       VLANs configuradas.
- get_port_status():  estado detallado de un puerto (ej. "1/1/1").

Sesión: POST /rest/<versión>/login (cookie + token CSRF en firmware 10.09+)
y POST /logout al terminar cada operación, porque AOS-CX limita las
sesiones REST simultáneas por usuario.

Las credenciales SIEMPRE provienen de variables de entorno RUVIC_ARUBA_CX_*
(ver config.ArubaCxConfig.from_env). Prohibido hardcodearlas.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator
from urllib.parse import quote

import requests
import urllib3

from .config import ArubaCxConfig
from .exceptions import ArubaCxAuthError, ArubaCxDataError, ArubaCxNetworkError
from .logging_utils import get_logger

_VERSION_RE = re.compile(r"^v\d+\.\d+$")
_PORT_RE = re.compile(r"^[0-9a-zA-Z/:._-]{1,32}$")
_IFACE_ATTRS = ("name,description,admin_state,link_state,link_speed,mtu,type,"
                "vlan_mode,vlan_tag,ipv4_address")


def _mbps(speed: Any) -> int | None:
    try:
        return int(speed) // 1_000_000
    except (TypeError, ValueError):
        return None


def _vlan_ref(value: Any) -> Any:
    # vlan_tag llega como {"10": "/rest/v10.09/system/vlans/10"} o como URI
    if isinstance(value, dict):
        keys = list(value)
        return int(keys[0]) if keys and keys[0].isdigit() else keys
    if isinstance(value, str):
        return value.rstrip("/").rsplit("/", 1)[-1]
    return value


class ArubaCxClient:
    """Cliente de consulta de un switch AOS-CX.

    Args:
        config: configuración. Si se omite, se lee de RUVIC_ARUBA_CX_*.

    Ejemplo:
        >>> client = ArubaCxClient()
        >>> client.get_port_status("1/1/1")
        {'name': '1/1/1', 'admin_state': 'up', 'link_state': 'up', 'speed_mbps': 1000, ...}
    """

    def __init__(self, config: ArubaCxConfig | None = None) -> None:
        self.config = config or ArubaCxConfig.from_env()
        if not _VERSION_RE.match(self.config.api_version):
            raise ArubaCxDataError(
                f"api_version {self.config.api_version!r} inválida: usa el formato v10.09, v10.13, etc."
            )
        self.base = f"{self.config.host}/rest/{self.config.api_version}"
        self._logger = get_logger()
        if not self.config.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ------------------------------------------------------------------ #
    # Sesión
    # ------------------------------------------------------------------ #

    @contextmanager
    def _session(self) -> Iterator[requests.Session]:
        s = requests.Session()
        s.verify = self.config.verify_ssl
        try:
            resp = s.post(
                f"{self.base}/login",
                data={"username": self.config.username, "password": self.config.password},
                headers={"x-use-csrf-token": "true"},
                timeout=self.config.connect_timeout,
            )
        except requests.exceptions.SSLError as exc:
            raise ArubaCxNetworkError(
                "Error de certificado SSL. Si el switch usa un certificado autofirmado, desactiva "
                "'Verificar certificado SSL' en la configuración del conector."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ArubaCxNetworkError(f"No se pudo alcanzar el switch {self.config.host}: {exc}") from exc
        if resp.status_code == 401:
            raise ArubaCxAuthError("Usuario o contraseña inválidos para la API REST del switch.")
        if resp.status_code == 403:
            raise ArubaCxAuthError("El usuario no tiene acceso a la API REST (revisa 'https-server rest access-mode').")
        if resp.status_code == 404:
            raise ArubaCxDataError(
                f"La versión de API {self.config.api_version} no existe en este switch. "
                f"Consulta {self.config.host}/rest para ver las disponibles."
            )
        if resp.status_code == 503 or "session limit" in (resp.text or "").lower():
            raise ArubaCxNetworkError("El switch alcanzó el límite de sesiones REST; reintenta en unos minutos.")
        if resp.status_code >= 400:
            raise ArubaCxDataError(f"El switch rechazó el login ({resp.status_code}): {resp.text[:200]}")
        csrf = resp.headers.get("x-csrf-token")
        if csrf:
            s.headers["x-csrf-token"] = csrf
        try:
            yield s
        finally:
            try:
                s.post(f"{self.base}/logout", timeout=self.config.connect_timeout)
            except requests.exceptions.RequestException:
                self._logger.warning("No se pudo cerrar la sesión REST; expirará sola en 20 minutos")
            s.close()

    def _get(self, s: requests.Session, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            resp = s.get(f"{self.base}{path}", params=params, timeout=self.config.connect_timeout)
        except requests.exceptions.RequestException as exc:
            raise ArubaCxNetworkError(f"Error de red consultando {path}: {exc}") from exc
        if resp.status_code in (401, 403):
            raise ArubaCxAuthError("La sesión fue rechazada o el usuario no tiene permiso de lectura.")
        if resp.status_code == 404:
            raise ArubaCxDataError(f"No existe {path.rsplit('/', 1)[-1]!r} en el switch.")
        if resp.status_code >= 400:
            raise ArubaCxDataError(f"El switch respondió {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def ping(self) -> bool:
        """Verifica credenciales iniciando sesión y leyendo el hostname.

        Raises:
            ArubaCxAuthError / ArubaCxNetworkError / ArubaCxDataError.
        """
        with self._session() as s:
            info = self._get(s, "/system", {"attributes": "hostname"})
        self._logger.info("Ping exitoso al switch %s", info.get("hostname"))
        return True

    # ------------------------------------------------------------------ #
    # Capacidad 1: información del switch
    # ------------------------------------------------------------------ #

    def get_switch_info(self) -> dict[str, Any]:
        """Consulta la información general del switch.

        Returns:
            Dict con hostname, platform, firmware, serial, boot_time (epoch), mgmt_ip.

        Ejemplo:
            >>> client.get_switch_info()
            {'hostname': 'core-sw-01', 'platform': '6300', 'firmware': 'FL.10.13.1000', ...}
        """
        with self._session() as s:
            data = self._get(s, "/system", {
                "attributes": "hostname,platform_name,firmware_version,boot_time,mgmt_intf_status,other_config"})
        mgmt = data.get("mgmt_intf_status") or {}
        return {
            "hostname": data.get("hostname"),
            "platform": data.get("platform_name"),
            "firmware": data.get("firmware_version"),
            "serial": (data.get("other_config") or {}).get("system_serial_number"),
            "boot_time": data.get("boot_time"),
            "mgmt_ip": mgmt.get("ip") or mgmt.get("ipv4_address"),
        }

    # ------------------------------------------------------------------ #
    # Capacidad 2: interfaces
    # ------------------------------------------------------------------ #

    def list_interfaces(self, only_up: bool = False, physical_only: bool = True) -> list[dict[str, Any]]:
        """Lista las interfaces con su estado.

        Args:
            only_up: si True, solo las que tienen enlace activo.
            physical_only: si True (default), omite VLAN, loopback y LAG.

        Returns:
            Lista de dicts: name, description, admin_state, link_state,
            speed_mbps, vlan_mode, access_vlan, type.

        Ejemplo:
            >>> client.list_interfaces(only_up=True)
            [{'name': '1/1/1', 'link_state': 'up', 'speed_mbps': 1000, ...}]
        """
        with self._session() as s:
            data = self._get(s, "/system/interfaces", {"depth": 2, "attributes": _IFACE_ATTRS})
        items = data.values() if isinstance(data, dict) else data
        out = []
        for i in items:
            if not isinstance(i, dict):
                continue
            if physical_only and i.get("type") not in (None, "system"):
                continue
            if only_up and i.get("link_state") != "up":
                continue
            out.append({
                "name": i.get("name"),
                "description": i.get("description"),
                "admin_state": i.get("admin_state"),
                "link_state": i.get("link_state"),
                "speed_mbps": _mbps(i.get("link_speed")),
                "vlan_mode": i.get("vlan_mode"),
                "access_vlan": _vlan_ref(i.get("vlan_tag")),
                "type": i.get("type"),
            })
        out.sort(key=lambda x: [int(p) if p.isdigit() else p for p in re.split(r"[/:]", str(x["name"]))])
        self._logger.info("Interfaces listadas: %d", len(out))
        return out

    # ------------------------------------------------------------------ #
    # Capacidad 3: VLANs
    # ------------------------------------------------------------------ #

    def list_vlans(self) -> list[dict[str, Any]]:
        """Lista las VLANs configuradas.

        Returns:
            Lista de dicts: id, name, admin_state, oper_state, description.

        Ejemplo:
            >>> client.list_vlans()
            [{'id': 1, 'name': 'DEFAULT_VLAN_1', 'oper_state': 'up', ...}]
        """
        with self._session() as s:
            data = self._get(s, "/system/vlans", {"depth": 2, "attributes": "id,name,admin,oper_state,description"})
        items = data.values() if isinstance(data, dict) else data
        out = [{
            "id": v.get("id"),
            "name": v.get("name"),
            "admin_state": v.get("admin"),
            "oper_state": v.get("oper_state"),
            "description": v.get("description"),
        } for v in items if isinstance(v, dict)]
        out.sort(key=lambda v: v["id"] if isinstance(v["id"], int) else 0)
        return out

    # ------------------------------------------------------------------ #
    # Capacidad 4: estado de un puerto
    # ------------------------------------------------------------------ #

    def get_port_status(self, port: str) -> dict[str, Any]:
        """Consulta el estado detallado de un puerto.

        Args:
            port: nombre del puerto, ej. "1/1/1".

        Returns:
            Dict con name, description, admin_state, link_state, speed_mbps,
            duplex, mtu, vlan_mode, access_vlan, rx_packets, tx_packets,
            rx_errors, tx_errors.

        Ejemplo:
            >>> client.get_port_status("1/1/24")
            {'name': '1/1/24', 'link_state': 'down', 'rx_errors': 0, ...}
        """
        if not isinstance(port, str) or not _PORT_RE.match(port.strip()):
            raise ArubaCxDataError(f"port inválido: {port!r}. Usa el formato miembro/slot/puerto, ej. 1/1/1.")
        name = port.strip()
        with self._session() as s:
            i = self._get(s, f"/system/interfaces/{quote(name, safe='')}", {"depth": 1})
        stats = i.get("statistics") or {}
        return {
            "name": i.get("name", name),
            "description": i.get("description"),
            "admin_state": i.get("admin_state"),
            "link_state": i.get("link_state"),
            "speed_mbps": _mbps(i.get("link_speed")),
            "duplex": i.get("duplex"),
            "mtu": i.get("mtu"),
            "vlan_mode": i.get("vlan_mode"),
            "access_vlan": _vlan_ref(i.get("vlan_tag")),
            "rx_packets": stats.get("rx_packets"),
            "tx_packets": stats.get("tx_packets"),
            "rx_errors": stats.get("rx_error") or stats.get("rx_errors"),
            "tx_errors": stats.get("tx_error") or stats.get("tx_errors"),
        }
