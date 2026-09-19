@echo off
title Restaurant POS - Starting Frontend + Backend
echo ============================================
echo   Restaurant POS - Starting All Services
echo ============================================
echo.

:: Start Backend in new window
echo [1/2] Starting Backend (uvicorn on port 8001)...
start "POS Backend" cmd /c "cd /d D:\pos\backend && C:\Users\share\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"

:: Wait for backend to be ready
echo Waiting 3 seconds for backend to initialize...
timeout /t 3 /nobreak >nul

:: Start Frontend in new window
echo [2/2] Starting Frontend (vite dev server)...
start "POS Frontend" cmd /c "cd /d D:\pos\frontend && npm run dev"

echo.
echo ============================================
echo   Both services started!
echo   Backend:  http://127.0.0.1:8001
echo   Frontend: http://localhost:5173
echo ============================================
echo.
echo Press any key to stop this window (services run in background)...
pause >nul
