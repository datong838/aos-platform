import importlib.util
from pathlib import Path
import pytest
p=Path(__file__).with_name('socket_migrate159.py');s=importlib.util.spec_from_file_location('sm159',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
@pytest.mark.parametrize('step',[158,159])
def test_exact_previous_isolated_unix_identity(step):assert m.require_step(step,'123','123','aos_current_preview_20260927','a0v_'+str(step-1),None) is None
@pytest.mark.parametrize('change',[(0,157),(0,160),(0,True),(1,'unbound'),(2,'999'),(3,'aos_meta_head'),(4,'a0v_159'),(5,'127.0.0.1')])
def test_wrong_step_cluster_database_version_or_tcp_cannot_execute(change):
 values=[158,'123','123','aos_current_preview_20260927','a0v_157',None];values[change[0]]=change[1]
 with pytest.raises(ValueError):m.require_step(*values)
