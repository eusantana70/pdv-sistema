@echo off
chcp 65001 >nul
echo Encerrando PDV Lumina...
call :matar 3000
call :matar 8000
call :matar 5173
taskkill /FI "WINDOWTITLE eq PDV Mock*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq PDV API*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq PDV Front*" /F >nul 2>&1
timeout /t 1 /nobreak >nul
echo.
echo Tudo encerrado.
pause
exit /b 0

:matar
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%~1 .*LISTENING"') do (
    taskkill /F /PID %%P >nul 2>&1
)
goto :eof
