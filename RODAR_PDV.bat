@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   PDV Lumina - iniciando
echo ============================================

echo [0/3] liberando portas 3000, 8000 e 5173...
call :liberar 3000
call :liberar 8000
call :liberar 5173
timeout /t 1 /nobreak >nul

echo [1/3] Mock SEFAZ :3000
start "PDV Mock :3000" /D "%~dp0mock-sefaz" cmd /k node server.js

echo [2/3] API :8000
start "PDV API :8000" /D "%~dp0" cmd /k ".venv\Scripts\python.exe scripts\run_api.py"

echo      aguardando a API responder...
set /a tentativas=0
:espera_api
timeout /t 1 /nobreak >nul
set /a tentativas+=1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto api_pronta
if %tentativas% lss 25 goto espera_api
echo.
echo [ERRO] A API nao respondeu na porta 8000.
echo        Veja a janela "PDV API :8000" ou o log data\api.log.
echo.
pause
exit /b 1

:api_pronta
echo      API respondendo OK

echo [3/3] Frontend :5173
if not exist "%~dp0frontend\node_modules" (
  echo      instalando dependencias do frontend...
  call npm --prefix "%~dp0frontend" install
)
start "PDV Front :5173" /D "%~dp0frontend" cmd /k npm run dev

echo      aguardando o frontend responder...
set /a tentativas=0
:espera_front
timeout /t 1 /nobreak >nul
set /a tentativas+=1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -TimeoutSec 3 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto front_pronto
if %tentativas% lss 40 goto espera_front
echo.
echo [ERRO] O frontend nao respondeu na porta 5173.
echo        Veja a janela "PDV Front :5173".
echo.
pause
exit /b 1

:front_pronto
echo      Frontend respondendo OK
start "" "http://localhost:5173"

echo.
echo ============================================
echo   Pronto!
echo   Front : http://localhost:5173
echo   API   : http://127.0.0.1:8000/api/health
echo   Mock  : http://127.0.0.1:3000/health
echo   Login : use suas credenciais (veja Configuracoes > Pessoas)
echo   Log   : data\api.log
echo ============================================
echo.
pause
exit /b 0

:liberar
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%~1 .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
goto :eof
