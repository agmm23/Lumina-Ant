# Cómo ejecutar Lumina_Ant

## Requisitos previos

- Python 3.11 o superior instalado
- API Key de Anthropic (para los análisis con IA)

---

## Primera vez (configuración inicial)

Solo necesitas hacer esto una vez.

### 1. Abrir terminal en la carpeta del proyecto

```
c:\$alfonso\Proyectos\files\Lumina_Ant\Lumina_Ant\
```

### 2. Entrar a la carpeta backend

```bash
cd backend
```

### 3. Crear el entorno virtual (si no existe)

```bash
python -m venv venv
```

> Si la carpeta `venv/` ya existe, omite este paso.

### 4. Activar el entorno virtual

**CMD (Símbolo del sistema):**cd
```cmd
venv\Scripts\activate
```

**PowerShell:**
```powershell
venv\Scripts\Activate.ps1
```

**Git Bash:**
```bash
source venv/Scripts/activate
```

Sabrás que está activado porque el prompt cambia a:
```
(venv) C:\...\backend>
```

### 5. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 6. Configurar variables de entorno

El archivo `.env` ya existe. Si necesitas editarlo:

```bash
# Abrir con notepad (CMD)
notepad .env
```

Contenido del `.env`:
```
ANTHROPIC_API_KEY=sk-ant-api03-tu-key-aqui
DEBUG=True
DATABASE_URL=sqlite:///./lumina_ant.db
```

> Sin la API key de Anthropic el sistema funciona en **modo demo** con datos simulados.

---

## Uso diario (arrancar el servidor)

Cada vez que quieras usar la aplicación:

### 1. Abrir terminal y entrar a la carpeta backend

```bash
cd backend
```

### 2. Activar el entorno virtual

**CMD:**
```cmd
venv\Scripts\activate
```

**PowerShell:**
```powershell
venv\Scripts\Activate.ps1
```

**Git Bash:**
```bash
source venv/Scripts/activate start
```

### 3. Iniciar el servidor

```bash
python -m uvicorn app.main:app --reload --port 8000
```

El servidor estará disponible en:
- **API:** http://localhost:8000
- **Swagger (documentación interactiva):** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### 4. Detener el servidor

Presiona `Ctrl + C` en la terminal donde corre el servidor.

---

## Cargar datos de ejemplo

Con el servidor corriendo, puedes cargar los archivos CSV de ejemplo desde la raíz del proyecto.

Abre http://localhost:8000/docs y usa los endpoints:

| Datasource   | Endpoint                          | Archivo CSV               |
|--------------|-----------------------------------|---------------------------|
| Ventas       | POST /api/ventas/upload-csv       | ventas_ejemplo.csv        |
| Gastos       | POST /api/gastos/upload-csv       | gastos_ejemplo.csv        |
| Inventario   | POST /api/inventarios/upload-csv  | inventario_ejemplo.csv    |
| Clientes     | POST /api/clientes/upload-csv     | clientes_ejemplo.csv      |

---

## Solución de problemas comunes

### "No module named ..."
El entorno virtual no está activado o faltan dependencias.
```bash
# Activar venv y reinstalar
venv\Scripts\activate
pip install -r requirements.txt
```

### "Address already in use" / Puerto ocupado
Ya hay un servidor corriendo. Dos opciones:

**Opción A:** Cerrar la terminal anterior donde corre el servidor (o Ctrl+C en ella).

**Opción B:** Usar un puerto diferente:
```bash
python -m uvicorn app.main:app --reload --port 8001
```
Y acceder en http://localhost:8001/docs

### PowerShell dice "no se puede cargar el archivo"
Ejecutar PowerShell como administrador y correr:
```powershell
Set-ExecutionPolicy RemoteSigned
```

### La IA responde en "modo demo"
La `ANTHROPIC_API_KEY` no está configurada en el `.env`. Agregar la key real para obtener análisis con IA.

---

## Estructura de carpetas relevante

```
Lumina_Ant/
├── backend/
│   ├── venv/               ← Entorno virtual (no subir a git)
│   ├── app/                ← Código de la aplicación
│   ├── .env                ← Variables de entorno (no subir a git)
│   ├── .env.example        ← Plantilla del .env
│   └── requirements.txt    ← Lista de dependencias
├── ventas_ejemplo.csv
├── gastos_ejemplo.csv
├── inventario_ejemplo.csv
├── clientes_ejemplo.csv
└── EJECUTAR.md             ← Este archivo
```
