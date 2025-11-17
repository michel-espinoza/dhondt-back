# API Backend - Diplomado

Proyecto Flask para backend API con CORS habilitado.

## Requisitos previos

- Python 3.8 o superior
- pip

## Instalación

1. **Crear entorno virtual:**
```powershell
python -m venv venv
```

2. **Activar entorno virtual:**
```powershell
.\venv\Scripts\Activate.ps1
```

3. **Instalar dependencias:**
```powershell
pip install -r requirements.txt
```

## Ejecutar la aplicación

```powershell
python run.py
```

La API estará disponible en `http://localhost:5000`

## Endpoints disponibles

### GET /api/saludo
Devuelve un saludo "Hola Mundo"

**Respuesta:**
```json
{
  "mensaje": "Hola Mundo",
  "status": "success"
}
```

### GET /api/health
Health check de la API

**Respuesta:**
```json
{
  "status": "healthy",
  "message": "API funcionando correctamente"
}
```

## CORS

CORS está habilitado para todas las rutas. Puedes hacer requests desde cualquier origen.

## Estructura del proyecto

```
back-diplomado/
├── app/
│   ├── __init__.py
│   └── api/
│       ├── __init__.py
│       └── routes.py
├── config/
├── config.py
├── run.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```
