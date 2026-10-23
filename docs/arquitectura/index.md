# Arquitectura

ERP Victoria es un monolito modular en capas, desplegado como SaaS con una base de datos por cliente.

```
Front web (React)        Agentes de IA
        \                 /
         API /api/v1 (FastAPI)
   autenticación · permisos · auditoría
                 |
  Módulos de negocio  <-->  Localización por país
                 |
   PostgreSQL · una base de datos por cliente
```

## Principios

- **Capas:** ninguna pantalla accede a la base de datos; todo pasa por la API.
- **Módulos aislados:** un módulo usa a otro solo mediante sus servicios.
- **Seguridad RBAC:** usuario → roles → permisos `modulo.objeto.accion`; auditoría de todo cambio.
- **Localización desacoplada:** cada país es un paquete; agregar un país no toca el núcleo.
- **Preparado para IA:** los agentes usan la misma API con los permisos del usuario.

Detalle de cada decisión en la sección [Decisiones (ADR)](../adr/0001-stack.md).
