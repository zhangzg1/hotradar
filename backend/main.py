import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径，支持在 backend 目录下启动
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import uvicorn
from backend.core.server import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=[str(_project_root)])