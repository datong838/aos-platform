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

@pytest.mark.parametrize('instance_id,logic',[('ecommerce.customer_service.default','S01'),('ecommerce.private_domain_manager.default','P01'),('ecommerce.content_officer.default','C06'),('ecommerce.campaign_planner.default','A02'),('ecommerce.shopping_advisor.default','G06')])
def test_role_accepts_own_logic_and_rejects_unrelated_logic(instance_id,logic):
    instance=NS(instance_id=instance_id,template=NS(content_hash='a'*64))
    template=NS(template_id=instance_id.removesuffix('.default'),content_hash='a'*64,lifecycle=NS(value='published'),manifest={'logicIds':[logic]})
    require_template(instance,template,instance_id)
    template.manifest['logicIds']=['D01']
    with pytest.raises(ValueError):require_template(instance,template,instance_id)


def test_wrong_role_skill_mapping_stops_before_database():
    from a0v_firstchain_skill_bindings import bind_items
    with pytest.raises(ValueError,match='ROLE_SKILL_MAPPING'):
        bind_items(None,None,[('ecommerce.skill.D01',None,None,None)],'ecommerce.content_officer.default',database='aos_meta_head')
