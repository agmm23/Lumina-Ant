@echo off
setlocal enabledelayedexpansion

REM Lumina_Ant - Script de Instalacion Automatica para Windows

echo ========================================
echo    Lumina_Ant - Instalacion Automatica
echo ========================================
echo.

if not exist "app" (
    echo ERROR: Debes ejecutar este script desde la carpeta /backend
    echo.
    echo Uso:
    echo   cd Lumina_Ant\backend
    echo   setup.bat
    pause
    exit /b 1
)

echo [0/5] Verificando Rust y Cargo...
set "CARGO_BIN=%USERPROFILE%\.cargo\bin"
set "PATH=!CARGO_BIN!;!PATH!"

"!CARGO_BIN!\cargo.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ADVERTENCIA: Cargo no encontrado. Instalando Rust...
    curl --proto =https --tlsv1.2 -sSf https://win.rustup.rs -o rustup-init.exe
    if errorlevel 1 (
        echo ERROR: No se pudo descargar Rust. Instala desde https://rustup.rs
        pause
        exit /b 1
    )
    rustup-init.exe -y --default-toolchain stable
    del rustup-init.exe
    set "PATH=!CARGO_BIN!;!PATH!"
    "!CARGO_BIN!\cargo.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: No se pudo instalar Rust. Instala manualmente desde https://rustup.rs
        pause
        exit /b 1
    )
)
echo Cargo OK:
"!CARGO_BIN!\cargo.exe" --version

echo [1/5] Creando entorno virtual...
python -m venv venv
if errorlevel 1 (
    echo ERROR: No se pudo crear el entorno virtual
    pause
    exit /b 1
)

echo [2/5] Activando entorno virtual...
call venv\Scripts\activate.bat
set "PATH=!CARGO_BIN!;!PATH!"

echo [3/5] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias
    pause
    exit /b 1
)

echo [4/5] Configurando variables de entorno...
if not exist ".env" (
    copy .env.example .env
    echo Archivo .env creado. IMPORTANTE: Edita .env y agrega tu ANTHROPIC_API_KEY
) else (
    echo Archivo .env ya existe, no se sobreescribira
)

echo [5/5] Verificando instalacion...
python --version
echo.

echo ========================================
echo    INSTALACION COMPLETADA
echo ========================================
echo.
echo PROXIMO PASO:
echo 1. Edita el archivo .env y agrega tu API key:
echo    notepad .env
echo.
echo 2. Ejecuta la aplicacion:
echo    python -m uvicorn app.main:app --reload
echo.
echo 3. Abre en tu navegador:
echo    http://localhost:8000/docs
echo.
echo ========================================

pause
endlocal
