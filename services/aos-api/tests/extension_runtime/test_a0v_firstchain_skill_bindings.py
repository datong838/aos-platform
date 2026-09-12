from pathlib import Path
from types import SimpleNamespace as NS
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from a0v_firstchain_skill_bindings import require_template,INSTANCE

@pytest.mark.parametrize('fault',[None,'instance','template','hash','unpublished','coverage'])
def test_advisor_activation_requires_exact_template_and_firstchain_coverage(fault):
    instance=NS(instance_id=INSTANCE,template=NS(content_hash='a'*64))
    template=NS(template_id='ecommerce.data_advisor',content_hash='a'*64,lifecycle=NS(value='published'),manifest={'logicIds':['D01','D02','D03']})
    if fault=='instance':instance.instance_id='other'
    if fault=='template':template.template_id='other'
    if fault=='hash':template.content_hash='b'*64
    if fault=='unpublished':template.lifecycle.value='evaluated'
    if fault=='coverage':template.manifest['logicIds']=['D01']
    if fault:
        with pytest.raises(ValueError,match='EXACT_ADVISOR'):require_template(instance,template)
    else:require_template(instance,template)
