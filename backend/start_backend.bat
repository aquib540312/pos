@echo off
cd /d D:\pos\backend
C:\Users\share\AppData\Local\Programs\Python\Python311\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 >> D:\pos\backend\uvicorn.out.log 2>&1