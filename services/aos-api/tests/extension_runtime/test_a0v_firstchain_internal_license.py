from pathlib import Path
from types import SimpleNamespace as NS
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
from a0v_firstchain_internal_license import require_internal_skills


@pytest.mark.parametrize('fault',['license','tenant','unpublished','revision','missing',None])
def test_license_is_limited_to_exact_internal_published_skills(fault):
    skills=[NS(skill_id='ecommerce.skill.'+s,revision=2,lifecycle=NS(value='published'),
        source_license='internal',publication_tenant=NS(org_id='org-org',project_id='dev-project')) for s in ('D01','D02','D03')]
    if fault=='license': skills[0].source_license='unknown'
    if fault=='tenant': skills[0].publication_tenant.org_id='dev-org'
    if fault=='unpublished': skills[0].lifecycle.value='evaluated'
    if fault=='revision': skills[0].revision=1
    if fault=='missing': skills.pop()
    if fault:
        with pytest.raises(ValueError,match='INTERNAL_LICENSE_'):
            require_internal_skills(skills)
    else: require_internal_skills(skills)


def test_explicit_successor_internal_revision_is_checked():
    from types import SimpleNamespace as NS
    import a0v_firstchain_internal_license as m
    skills=[NS(skill_id='ecommerce.skill.'+s,revision=3,lifecycle=NS(value='published'),
        source_license='internal',publication_tenant=NS(org_id='org-org',project_id='dev-project')) for s in ('D01','D02','D03')]
    m.require_internal_skills(skills,skill_revision=3)
    with pytest.raises(ValueError):m.require_internal_skills(skills)
    with pytest.raises(ValueError):m.require_internal_skills(skills,skill_revision=4)
