# Victoria ERP

ERP SaaS modular para medianas empresas de Latinoamérica, con núcleo en Compras y SCM y preparado para agentes de IA.

## Estructura

```
erp-victoria/
├── backend/            API y lógica de negocio (Python + FastAPI)
│   ├── app/
│   │   ├── api/v1/     Rutas públicas versionadas
│   │   ├── core/       Configuración, base de datos, seguridad común
│   │   └── modules/    Un paquete por módulo de negocio
│   └── tests/
├── frontend/           Interfaz web (React + TypeScript + Vite)
├── docs/               Portal de documentación (MkDocs)
├── docker-compose.yml  Levanta BD + API + front en local
└── mkdocs.yml
```

## Requisitos

- Docker Desktop (gratuito para uso personal y pequeñas empresas)
- Git
- Opcional para desarrollo sin Docker: Python 3.12+ y Node 20+

## Levantar el entorno local

```bash
cp .env.example .env
docker compose up --build
```

| Servicio | URL |
| --- | --- |
| Front | http://localhost:5173 |
| API | http://localhost:8000/api/v1/health |
| Documentación de la API | http://localhost:8000/docs |

Usuario inicial: `admin@erp-victoria.local` / `Admin123!` (cámbialo en `.env` antes de usarlo fuera de tu equipo).

Si ya tenías el ambiente levantado de la semana 1, reconstrúyelo con `docker compose up --build`.

## Documentación

```bash
pip install "mkdocs<2" mkdocs-material
mkdocs serve
```

Se publica automáticamente en GitHub Pages en cada cambio a la rama `main`.

## Pruebas

```bash
cd backend
pip install ".[dev]"
pytest
```

## Convenciones

Ver [docs/arquitectura/convenciones.md](docs/arquitectura/convenciones.md).
