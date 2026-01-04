import re
import urllib.parse


def is_valid_whatsapp(number):
    if not number:
        return False
    if not re.fullmatch(r"\d+", number):
        return False
    return 9 <= len(number) <= 15


def generate_wa_link(number):
    if not number:
        return ""
    return f"https://wa.me/{number}"


def generate_wa_prefilled_link(number, message):
    if not number:
        return ""
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{number}?text={encoded}"


def generate_maps_link(address_line, city, region, country):
    parts = [address_line, city, region, country]
    joined = ", ".join([p for p in parts if p])
    encoded = urllib.parse.quote(joined)
    return f"https://www.google.com/maps/search/?api=1&query={encoded}"


def allowed_image_extension(filename):
    return filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))


def lead_statuses():
    return [
        "NUEVO",
        "CONTACTADO",
        "DEMO_AGENDADA",
        "DEMO_REALIZADA",
        "VENTA_CERRADA",
        "NO_INTERESADO",
    ]


def lead_status_labels():
    return {
        "NUEVO": "Nuevo",
        "CONTACTADO": "Contactado",
        "DEMO_AGENDADA": "Demo Agendada",
        "DEMO_REALIZADA": "Demo Realizada",
        "VENTA_CERRADA": "Venta Cerrada",
        "NO_INTERESADO": "No Interesado",
    }


def demo_assignable_roles():
    return {"JEFE", "VENDEDOR"}


def user_roles():
    return ["ADMIN", "JEFE", "VENDEDOR", "RECLUTA"]


def user_statuses():
    return ["ACTIVO", "PAUSADO", "BLOQUEADO", "PENDIENTE"]
