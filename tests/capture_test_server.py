"""Browser regression fixture: synthetic image, no medical data or model weights."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from scripts.serve_app import AppServer

if __name__=='__main__':
    server=AppServer(('127.0.0.1',0))
    server.set_session(Image.new('RGB',(400,320),(40,70,90)),[],'desktop-test.jpg')
    server.on_capture=lambda data:None
    print(f'READY {server.server_port}',flush=True)
    try:server.serve_forever()
    finally:server.server_close()
