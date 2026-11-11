import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
os.environ.setdefault('REGMAIL_SENDER','sender@example.test')
os.environ.setdefault('REGMAIL_RECIPIENT','recipient@example.test')

