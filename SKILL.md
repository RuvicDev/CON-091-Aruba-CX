---
name: aruba-cx
description: >
  Usa la librería ruvic_aruba_cx_connector para consultar (solo lectura)
  switches HPE Aruba CX con AOS-CX - información del switch
  (get_switch_info), interfaces y su estado (list_interfaces), VLANs
  (list_vlans) y estado detallado de un puerto (get_port_status). Úsala
  cuando el usuario pregunte por puertos caídos, VLANs, interfaces,
  firmware o el estado de un switch Aruba CX.
triggers:
- aruba cx
- aos-cx
- switch
- puerto
- interfaces
- vlan
- estado del puerto
---

# Conector Aruba CX (ruvic_aruba_cx_connector)

Librería Python de solo lectura para la API REST de AOS-CX. Está **preinstalada en el runtime** cuando el
conector está configurado (si no, instálala con
`pip install git+https://github.com/RuvicDev/CON-091-Aruba-CX.git#subdirectory=lib`).

## Regla crítica de credenciales

El código generado **NUNCA hardcodea credenciales**. Siempre se leen de
variables de entorno, disponibles cuando el conector `aruba_cx` está
configurado:

| Variable | Contenido |
|----------|-----------|
| `RUVIC_ARUBA_CX_HOST` | URL del switch |
| `RUVIC_ARUBA_CX_USERNAME` | Usuario |
| `RUVIC_ARUBA_CX_PASSWORD` | Contraseña |
| `RUVIC_ARUBA_CX_API_VERSION` | (opcional) Versión de la API REST, default v10.09 |
| `RUVIC_ARUBA_CX_VERIFY_SSL` | (opcional) Verificar certificado SSL, default true |
| `RUVIC_ARUBA_CX_CONNECT_TIMEOUT` | (opcional) Timeout de conexión (segundos), default 15 |

Si estas variables NO existen, el conector no está configurado: no
generes código que lo use; indica al usuario que lo configure en
**Settings → Conectores**. El código generado **NUNCA** usa nombres con
segmento de alias (`_DEFAULT_INSTANCIA_`, `_PRODUCCION_`, etc.) salvo que
aparezcan en una sección autogenerada `## Variables en tu entorno` al final
de este skill.

## Este conector es de solo lectura

Ninguna operación cambia la configuración del switch. Cada operación
abre una sesión REST, consulta y la cierra, porque AOS-CX limita a 6
sesiones simultáneas por usuario: no llames al conector en bucles
rápidos sobre muchos puertos; usa `list_interfaces` una vez.

## Conexión (siempre igual)

```python
from ruvic_aruba_cx_connector import ArubaCxClient

client = ArubaCxClient()  # lee RUVIC_ARUBA_CX_* del entorno automáticamente
```

## Capacidad 1 — Información del switch

```python
info = client.get_switch_info()
print(info["hostname"], info["platform"], info["firmware"], info["serial"])
```

## Capacidad 2 — Listar interfaces

```python
caidas = [i for i in client.list_interfaces() if i["link_state"] != "up"]
for i in caidas:
    print(i["name"], i["admin_state"], i["link_state"], i["description"])
```

`only_up=True` devuelve solo las activas; `physical_only=False` incluye VLAN, loopback y LAG.

## Capacidad 3 — Listar VLANs

```python
for v in client.list_vlans():
    print(v["id"], v["name"], v["oper_state"])
```

## Capacidad 4 — Estado de un puerto

```python
p = client.get_port_status("1/1/24")
print(p["link_state"], p["speed_mbps"], p["access_vlan"], p["rx_errors"], p["tx_errors"])
```

## Manejo de errores

```python
from ruvic_aruba_cx_connector import (
    ArubaCxAuthError, ArubaCxDataError, ArubaCxNetworkError,
)

try:
    client.get_port_status("1/1/1")
except ArubaCxAuthError as e:
    print(f"Credenciales o permisos: {e}")
except ArubaCxNetworkError as e:
    print(f"No se pudo alcanzar el servicio: {e}")
except ArubaCxDataError as e:
    print(f"Error de datos: {e}")
```

Muestra el mensaje de la excepción tal cual al usuario: indica qué corregir.

## Buenas prácticas al generar código

1. Lee credenciales SOLO de las variables `RUVIC_ARUBA_CX_*` (el constructor de `ArubaCxClient` ya lo hace).
2. Nunca imprimas `RUVIC_ARUBA_CX_PASSWORD`.
3. Para revisar muchos puertos usa `list_interfaces()` una vez en vez de `get_port_status` en bucle (límite de sesiones).
4. Los nombres de puerto tienen el formato miembro/slot/puerto (ej. `1/1/1`).
5. Si el switch responde que la versión de API no existe, pide al usuario la versión correcta (ej. v10.13).
