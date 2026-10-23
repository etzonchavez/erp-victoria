"""Módulos de negocio. Cada módulo es un paquete con esta estructura:

    <modulo>/
        models.py    Tablas (SQLAlchemy)
        schemas.py   Entradas y salidas de la API (Pydantic)
        service.py   Reglas de negocio
        api.py       Rutas FastAPI

Regla: un módulo usa a otro solo a través de su service.py, nunca leyendo sus tablas.
"""
