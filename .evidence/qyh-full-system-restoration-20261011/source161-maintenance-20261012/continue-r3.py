import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('maintenance',p/'maintain.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
m.OUT=p/'r3'
m.CLONE_DB='qyh_source161_window_restore_r3_20261012'
m.main()
