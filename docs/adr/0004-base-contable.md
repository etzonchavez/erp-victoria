# ADR-004: Base contable configurable para compras y maestros

**Estado:** aprobado · 30 oct 2026

## Contexto

Las compras deben quedar alineadas con la contabilidad desde el primer día, aunque el módulo de Contabilidad completo (asientos, libros, cierre) llega en la Fase 1 (2027). Si artículos y categorías nacen sin estructura contable, habría que rediseñarlos después y migrar datos de clientes.

Además, en Perú el MEF aprobó el **PCGE 2026** (Resolución N.° 002-2026-EF/30), obligatorio desde el 1 de enero de 2028. Mantiene la estructura del PCGE Modificado 2019, pero obliga a que el plan de cuentas pueda actualizarse sin tocar el código.

## Decisión

Construir ahora una **contabilidad base de configuración**, sin asientos reales:

1. **Plan de cuentas por empresa**, cargado desde una **plantilla versionada por país** (Perú: `PCGE-2019` reducido) y editable. Cuentas jerárquicas; solo las cuentas *imputables* (último nivel) se usan en transacciones.
2. **Perfiles contables reutilizables**. Cada perfil define las cuentas de un tipo de compra (compra, existencia, variación, gasto, por pagar). Vienen 8 perfiles precargados (6 originales y, desde la versión 0.8.0, activo fijo de muebles y de maquinaria).
3. **Categorías de artículo jerárquicas** que apuntan a un perfil. Si una subcategoría no define uno, **hereda** el de su categoría padre.
4. **Artículo** con un tipo: bien inventariable, bien no inventariable, servicio o activo fijo. Sus cuentas salen de la categoría. Solo el contador (permiso `contabilidad.perfil.editar`) puede asignarle otro perfil en una empresa (excepción).
5. **Centros de costo** ligados a una unidad de negocio.
6. **Impuestos** (IGV 18 %, exonerado, inafecto) con su cuenta contable.
7. Cada línea de solicitud y orden de compra **guarda la combinación contable** vigente al crearse (cuenta + centro de costo). La orden muestra la **vista previa del asiento** (Debe/Haber) sin contabilizar.

## Regla de resolución de cuentas

```
perfil = articulo.perfil_excepcion
      ?? categoría del artículo (o el ancestro más cercano con perfil)
cuenta de cargo = según el tipo del artículo:
  bien inventariable     → perfil.cuenta_compra    (60x)  + destino 20x/24x/25x ↔ 61x
  bien no inventariable  → perfil.cuenta_gasto     (65x)
  servicio               → perfil.cuenta_gasto     (63x)
  activo fijo            → perfil.cuenta_existencia (33x)
impuesto                 → impuesto.cuenta          (40111)
cuenta por pagar         → perfil.cuenta_por_pagar  (4212 / 4654)
```

Un artículo no se puede guardar si su perfil no se resuelve o si el tipo del perfil no coincide con el tipo del artículo.

## Consecuencias

- **Despliegue rápido:** una empresa nueva queda operativa con la plantilla, los perfiles y las categorías de ejemplo ya asignadas; el contador solo ajusta.
- **Mantenible:** cambiar un perfil actualiza todas las categorías que lo usan. El PCGE 2026 se agrega como plantilla nueva (`PCGE-2026`) sin tocar el núcleo.
- **Multipaís:** cada país aporta su plantilla en el paquete de localización (`pe`, `co`…); el modelo es el mismo.
- **2027:** Contabilidad generará los asientos reales con la misma regla y la combinación ya guardada en cada línea; no hay rediseño.
- **Costo:** la Semana 3 crece. Si se atrasa, la carga desde Excel de proveedores y artículos pasa a la Semana 6 (regla de prioridad del plan).

## Alternativas descartadas

- **Cuentas directamente en cada artículo:** mucha carga de datos y errores; no escala.
- **Cuentas directamente en cada categoría, sin perfiles:** obliga a repetir las mismas 5 cuentas en decenas de categorías.
- **Contabilidad completa antes de la demo:** pone en riesgo la fecha del 4 de diciembre.
