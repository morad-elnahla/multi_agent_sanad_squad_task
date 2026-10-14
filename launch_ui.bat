@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "SANAD_PYTHON=.venv\Scripts\python.exe"
) else (
  set "SANAD_PYTHON=python"
)
"%SANAD_PYTHON%" -c "import streamlit, langgraph, langchain_openai" >nul 2>&1
if errorlevel 1 (
  echo Installing the user interface dependencies...
  "%SANAD_PYTHON%" -m pip install -r requirements.lock
  if errorlevel 1 (
    echo Installation failed. Please copy the error message for diagnosis.
    pause
    exit /b 1
  )
)
"%SANAD_PYTHON%" -m streamlit run app.py
pause
