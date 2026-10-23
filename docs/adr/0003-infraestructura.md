# ADR-003: Infraestructura a costo cero

**Estado:** aprobado · 23 oct 2026

## Decisión

Hasta conseguir inversión, el ERP se construye y despliega con costo cero; todo corre en Docker para migrar a un ambiente pagado sin cambiar código.

| Componente | Opción gratuita | Límite a vigilar |
| --- | --- | --- |
| Licencias | Software libre; Docker Desktop gratis para uso personal y pequeñas empresas | Ninguno en esta etapa |
| Servidor de demo | Oracle Cloud Always Free, VM Ampere A1 con Docker | 2 OCPU y 12 GB de RAM |
| BD alternativa | Neon, plan gratuito | 0.5 GB y 100 CU-hours por proyecto |
| Código, CI y docs | GitHub, GitHub Actions, GitHub Pages | Minutos de CI del plan gratuito |

## Reglas

- El ambiente gratuito sirve para demo y piloto controlado, no para datos reales de clientes.
- Con inversión: migrar a nube de pago con un ambiente por cliente.
