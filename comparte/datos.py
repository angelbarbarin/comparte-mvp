"""Datos de prueba del piloto simulado del AMG.

⚠️  Todos los nombres son ficticios. Las coordenadas son aproximadas de colonias y centros reales del AMG
solo para que las distancias sean verosímiles.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .modelos import Donante, Receptor, Voluntario

DONANTES = [
    # nombre, giro, municipio, lat, lon, contacto
    ("Panadería La Espiga", "panaderia", "Tlaquepaque", 20.6402, -103.3120, "Rosa Medina"),
    ("Supermercado Fresko Chapalita", "supermercado", "Guadalajara", 20.6685, -103.3920, "Jorge Salas"),
    ("Frutas Don Chuy (Abastos)", "mercado", "Guadalajara", 20.6525, -103.3610, "Jesús Cortés"),
    ("Restaurante Los Arcos", "restaurante", "Zapopan", 20.7215, -103.3860, "Elena Prieto"),
    ("Comedor Corporativo TechSur", "comedor_institucional", "Zapopan", 20.7105, -103.4130, "Raúl Íñiguez"),
    ("Tortillería La Güera", "tortilleria", "Tonalá", 20.6245, -103.2335, "Guadalupe Ramos"),
    ("Cocina Universitaria Campus Sur", "comedor_institucional", "Tlaquepaque", 20.6075, -103.4145, "Mónica Aguirre"),
    ("Supermercado La Canasta", "supermercado", "Tlajomulco", 20.4738, -103.4432, "Héctor Vela"),
    ("Verdulería El Campo", "verduleria", "Guadalajara", 20.6772, -103.3455, "Irma Duarte"),
    ("Hotel Plaza Real (cocina)", "hotel", "Guadalajara", 20.6935, -103.3895, "Chef Tomás Beltrán"),
]

RECEPTORES = [
    # nombre, tipo, municipio, lat, lon, cierra, necesidades {categoría: 1-3}, kg/día, kg de frío/día
    ("Banco de Alimentos Nueva Esperanza", "banco_alimentos", "Guadalajara", 20.6350, -103.3400, "19:00",
     {"pan": 2, "fruta": 3, "verdura": 3, "abarrotes": 3, "lacteos": 2, "proteina": 2, "preparado": 1}, 800, 200),
    ("Comedor Comunitario Santa Cecilia", "comedor", "Tonalá", 20.6270, -103.2430, "19:00",
     {"pan": 3, "verdura": 3, "fruta": 2, "abarrotes": 3, "preparado": 2}, 80, 0),
    ("Albergue Casa del Camino", "albergue", "Guadalajara", 20.7000, -103.3150, "23:59",
     {"preparado": 3, "proteina": 3, "lacteos": 2, "pan": 2, "fruta": 2, "verdura": 2}, 120, 30),
    ("Casa Hogar Semillas", "casa_hogar", "Zapopan", 20.7380, -103.4020, "21:00",
     {"lacteos": 3, "fruta": 3, "pan": 2, "abarrotes": 2, "verdura": 2}, 60, 15),
    ("Comedor Los Pinos", "comedor", "Tlajomulco", 20.4980, -103.4400, "18:00",
     {"verdura": 3, "abarrotes": 3, "pan": 2, "fruta": 2}, 100, 0),
]

VOLUNTARIOS = [
    # nombre, vehículo, capacidad kg, hielera, lat, lon
    ("Mariana López", "auto", 40, False, 20.6700, -103.3600),
    ("Carlos Ramírez", "camioneta", 300, True, 20.7150, -103.4000),
    ("Fernanda Ortiz", "moto", 15, False, 20.6450, -103.3200),
    ("Luis Hernández", "auto", 50, True, 20.6300, -103.2400),
    ("Sofía Mendoza", "camioneta", 200, False, 20.4900, -103.4450),
]


def sembrar(db: Session) -> bool:
    """Carga el piloto simulado si la base está vacía. Devuelve True si cargó."""
    if db.scalar(select(Donante.id).limit(1)) is not None:
        return False
    for n, g, m, la, lo, c in DONANTES:
        db.add(Donante(nombre=n, giro=g, municipio=m, lat=la, lon=lo, contacto=c))
    for n, t, m, la, lo, ci, nec, cap, frio in RECEPTORES:
        db.add(Receptor(nombre=n, tipo=t, municipio=m, lat=la, lon=lo, horario_cierre=ci, necesidades=nec,
                        capacidad_diaria_kg=cap, capacidad_frio_kg=frio))
    for n, v, cap, hiel, la, lo in VOLUNTARIOS:
        db.add(Voluntario(nombre=n, vehiculo=v, capacidad_kg=cap, tiene_hielera=hiel, lat=la, lon=lo))
    db.commit()
    return True
