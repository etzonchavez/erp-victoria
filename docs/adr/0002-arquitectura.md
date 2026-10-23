# ADR-002: Arquitectura

**Estado:** aprobado · 23 oct 2026

## Decisión

Monolito modular en capas, SaaS con una base de datos por cliente y localización por país desacoplada del núcleo.

## Detalle

- **Monolito modular:** cada módulo tiene sus tablas, servicios y API; un módulo usa a otro solo por sus servicios.
- **Ambiente por cliente:** mismo código, una base de datos por cliente, creado desde una plantilla automatizada.
- **Seguridad:** usuario → roles → permisos `modulo.objeto.accion`; el administrador activa módulos; acceso a datos por empresa y unidad de negocio; auditoría de todo cambio.
- **Localización:** paquete por país (`pe`, `co`, `pa`, `sv`, `cl`) con impuestos, comprobantes electrónicos, plan de cuentas y libros legales.
- **Estándares multipaís:** montos con moneda y decimal exacto, fechas en UTC, textos traducibles por clave, identificadores UUID, API versionada.
- **IA:** los agentes actúan con los permisos del usuario que los autoriza y cada acción queda auditada.
