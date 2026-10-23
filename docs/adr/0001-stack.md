# ADR-001: Stack tecnológico

**Estado:** aprobado · 23 oct 2026

## Decisión

Backend en Python con FastAPI, base de datos PostgreSQL y frontend en React con TypeScript.

| Capa | Tecnología |
| --- | --- |
| Front | React + TypeScript + Vite |
| API | FastAPI + Pydantic |
| Lógica | Python, SQLAlchemy, Alembic |
| Base de datos | PostgreSQL con pgvector |
| Seguridad | JWT + RBAC propio; Keycloak (SSO) en 2027 |
| Infraestructura | Docker, GitHub Actions |
| Documentación | MkDocs Material |

## Motivo

Python tiene el ecosistema de IA más fuerte y es donde la IA genera código de mayor calidad, clave para un equipo de una persona.

## Alternativas descartadas

- Java con Spring Boot: más lento de construir para una persona.
- Partir de Odoo: hereda su licencia y arquitectura, sin diferencial.
- Microservicios: costo operativo alto sin equipo.
