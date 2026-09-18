import sys, os
sys.path.insert(0, r'D:\pos\backend')
os.chdir(r'D:\pos\backend')
from app.main import app
import uvicorn
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
