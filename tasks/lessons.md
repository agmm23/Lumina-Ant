# Lessons Learned — Lumina Ant

Registro de errores recurrentes y sus correcciones. Revisar al inicio de cada sesión.

---

## Entorno y Paths

### L001 — El `$` en `$alfonso` es un bash variable
- **Error**: `cd /c/$alfonso/...` → bash interpreta `$alfonso` como variable vacía → "No such file"
- **Corrección**: Siempre escapar: `cd "/c/\$alfonso/..."` en Git Bash
- **En PowerShell**: usar backtick → `"C:\`$alfonso\..."`
- **Write/Read tools**: manejan el `$` literal correctamente, sin escapar

### L002 — `python -c` en bash con path `$alfonso`
- **Error**: `cd "C:/\$alfonso/..." && python -c ...` — el `\$` se procesa mal en algunos contextos
- **Corrección**: Usar `sys.path.insert` en lugar de `cd`: `python -c "import sys; sys.path.insert(0, 'C:/\$alfonso/...'); from app.main import app"`

---

## Edición de Archivos

### L003 — Leer antes de editar (siempre)
- **Error**: Llamar Edit sin haber llamado Read primero → "File has not been read yet"
- **Corrección**: Siempre Read el archivo antes del primer Edit en esa sesión, aunque solo sean las primeras líneas

### L004 — `old_string` debe ser único en el archivo
- **Error**: Edit falla si `old_string` aparece más de una vez
- **Corrección**: Incluir suficiente contexto circundante (líneas antes/después) para hacer el match único

### L005 — No usar `Remove-Item -Recurse -Force` con VS Code abierto
- **Error**: Elimina los archivos pero no el directorio raíz si VS Code lo tiene abierto
- **Corrección**: Cerrar VS Code primero, o usar `rm -rf` desde Git Bash

---

## Subagentes

### L006 — Los subagentes en este entorno no tienen permisos de escritura/bash por defecto
- **Error**: Delegar ediciones de archivos a subagentes → fallan porque no tienen Read/Edit/Bash aprobados
- **Corrección**: Usar subagentes solo para investigación/lectura. Las ediciones hacerlas directamente en el agente principal

---

## Backend / Python

### L007 — No usar `pd.read_csv()` directamente en routers
- **Patrón correcto**: Siempre pasar por `create_reader(source_type, contents)` de `data_reader.py`
- **Razón**: Centraliza la lógica multi-fuente (CSV/Excel/GSheets) y mantiene el contrato uniforme

### L008 — `save_and_watch()` requiere nuevos kwargs desde la actualización multi-fuente
- **Firma actual**: `save_and_watch(datasource_type, df, db, filename, source_type, sheet, original_file_content)`
- **Error previo**: Llamarlo con la firma antigua sin `source_type`/`sheet` → error de argumento

### L009 — `BytesIO` no es necesario en routers actualizados
- **Antes**: `df = pd.read_csv(BytesIO(contents))`
- **Ahora**: `reader = create_reader(source_type, contents); df = reader.read(sheet=...)`
- `BytesIO` ya no se necesita en los routers de upload

---

## Frontend / React

### L010 — Tailwind CSS v4 no tiene `tailwind.config.js`
- No intentar crear ni modificar ese archivo
- Las clases dark mode usan prefix `dark:` directamente
- La configuración va en `vite.config.js` via `@tailwindcss/vite`

### L011 — i18n: usar siempre `t()` para strings de UI
- **Patrón**: `const { t } = useLanguage()` al inicio del componente
- **Interpolación**: `t('key', { var: value })` para strings con variables
- **Fallback**: si la key no existe, `t()` retorna la key misma (no falla)
- **No** hardcodear strings en español en componentes — siempre pasar por `t()`

### L012 — `require` no existe en módulos ES (Vite)
- **Error**: Usar `require(...)` en archivos `.jsx` → ReferenceError en runtime
- **Corrección**: Usar `import` estático o dynamic `import()` para carga condicional

---

## Patrones a Seguir

### P001 — Agregar nueva fuente de datos
1. Crear clase en `data_reader.py` extendiendo `DataSourceReader`
2. Registrar en `create_reader()` factory
3. Agregar case en `detect_source_type()` si aplica
4. El resto del pipeline (parse/import/watcher) no necesita cambios

### P002 — Agregar nuevo proveedor de IA
1. Crear clase en `ai_provider.py` extendiendo `AIProvider`
2. Registrar en `get_provider()` factory de `ai_service.py`
3. Agregar opción en `config.py` y `.env.example`

### P003 — Agregar nueva página al frontend
1. Crear `src/pages/NuevaPagina.jsx` con `useLanguage()` desde el inicio
2. Agregar ruta en `App.jsx`
3. Agregar item en `Sidebar.jsx`
4. Agregar keys i18n en `locales/es.json` y `locales/en.json`
