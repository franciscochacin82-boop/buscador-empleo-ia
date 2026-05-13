@echo off
echo ============================================
echo   Buscador de Empleo con IA
echo   Para profesionales de Comunicaciones
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado. Descargalo en python.org
    pause
    exit /b 1
)

REM Install dependencies if needed
echo Instalando dependencias...
pip install -r requirements.txt --quiet

echo.
echo Iniciando la aplicacion...
echo Abrira en tu navegador en: http://localhost:8501
echo.
echo Para cerrar la app, presiona Ctrl+C aqui.
echo.

streamlit run app.py --server.headless false
pause
