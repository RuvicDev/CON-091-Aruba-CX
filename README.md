# Conector Aruba CX (CON-091)

Conector Ruvic de solo lectura para switches HPE Aruba CX (AOS-CX REST API v10.x): información del switch, interfaces, VLANs y estado de puertos.

## Instalación

```bash
pip install git+https://github.com/RuvicDev/CON-091-Aruba-CX.git#subdirectory=lib
```

Python 3.10+. Dependencias: `requests>=2.31,<3.0`.

## Permisos requeridos

Autenticación por **usuario y contraseña** (cookie de sesión + token CSRF en firmware 10.09+).

En el switch:

```
user ruvic-api group operators password plaintext <contraseña>
https-server rest access-mode read-only
https-server vrf mgmt
```

El grupo `operators` es de solo lectura. Ajusta el VRF al que usa tu red de gestión.

## Variables de entorno (`RUVIC_ARUBA_CX_*`)

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `RUVIC_ARUBA_CX_HOST` | Sí | URL del switch |
| `RUVIC_ARUBA_CX_USERNAME` | Sí | Usuario |
| `RUVIC_ARUBA_CX_PASSWORD` | Sí | Contraseña |
| `RUVIC_ARUBA_CX_API_VERSION` | No (default `v10.09`) | Versión de la API REST |
| `RUVIC_ARUBA_CX_VERIFY_SSL` | No (default `true`) | Verificar certificado SSL |
| `RUVIC_ARUBA_CX_CONNECT_TIMEOUT` | No (default `15`) | Timeout de conexión (segundos) |

Los campos opcionales vacíos usan su valor por defecto (la plataforma envía
`""` cuando un campo queda en blanco).

## Pruebas locales

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ./lib

export RUVIC_ARUBA_CX_HOST=...
export RUVIC_ARUBA_CX_USERNAME=...
export RUVIC_ARUBA_CX_PASSWORD=...

python test_connection.py
python validate_local.py
```

`validate_local.py` lee la información del switch, las interfaces caídas, las VLANs y el estado del primer puerto.

## Notas de integración

- Cada operación hace `POST /login` → consulta → `POST /logout`; si el logout falla, la sesión expira sola a los 20 minutos.
- El token CSRF (`x-csrf-token`) se pide con `x-use-csrf-token: true` y se reenvía en cada petición.
- Los nombres de puerto se codifican en la URL (`1/1/1` → `1%2F1%2F1`).
- `api_version` debe coincidir con una versión soportada por el firmware; consulta `https://<switch>/rest`.

## Limitaciones conocidas

- Solo lectura: no habilita/deshabilita puertos ni cambia VLANs.
- Un switch por instancia del conector; usa varias instancias (alias) para varios switches.
- AOS-CX limita a 6 sesiones REST simultáneas por usuario y 48 por switch.
