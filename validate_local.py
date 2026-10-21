"""Validación local del conector aruba_cx (solo lectura).

Uso:
    python validate_local.py

Requiere RUVIC_ARUBA_CX_HOST, RUVIC_ARUBA_CX_USERNAME y RUVIC_ARUBA_CX_PASSWORD
exportadas (y RUVIC_ARUBA_CX_VERIFY_SSL=false si el switch usa certificado autofirmado).
"""

from ruvic_aruba_cx_connector import ArubaCxClient, setup_logging

setup_logging("INFO")
client = ArubaCxClient()

print("== 1. Información del switch ==")
print(f"  {client.get_switch_info()}")

print("== 2. Interfaces caídas ==")
interfaces = client.list_interfaces()
for i in [i for i in interfaces if i["link_state"] != "up"][:10]:
    print(f"  {i['name']} admin={i['admin_state']} link={i['link_state']}")

print("== 3. VLANs ==")
for v in client.list_vlans():
    print(f"  {v['id']} {v['name']}")

print("== 4. Estado del primer puerto ==")
if interfaces:
    print(f"  {client.get_port_status(interfaces[0]['name'])}")

print("\nTodo OK.")
