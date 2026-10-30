"""最终全量后端验收：临时私有 Runner，模型调用须另行显式启用。"""
import os

from app.config import PROJECT_ROOT
from verify_stage03 import main

if __name__ == '__main__':
    # 两个 test_education.py 保留原名；importlib 避免模块名碰撞，显式路径供旧测试互用。
    paths = [PROJECT_ROOT / p for p in ('backend', 'backend/tests', 'backend/tests/integration')]
    os.environ['PYTHONPATH'] = os.pathsep.join([*(str(p) for p in paths),
                                              os.environ.get('PYTHONPATH', '')])
    os.environ['PYTEST_ADDOPTS'] = os.environ.get('PYTEST_ADDOPTS', '') + ' --import-mode=importlib'
    tests = sorted(str(p.relative_to(PROJECT_ROOT))
                   for p in (PROJECT_ROOT / 'backend/tests').rglob('test_*.py'))
    main(test_files=tests, default_prefix='stage06')
