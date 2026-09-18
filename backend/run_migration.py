import sys, os
sys.path.insert(0, r'D:\pos\backend')
os.chdir(r'D:\pos\backend')
from alembic.config import Config
from alembic import command
config = Config(r'D:\pos\backend\alembic.ini')
command.upgrade(config, 'head')
print('Migration OK')
