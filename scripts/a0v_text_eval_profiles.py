"""Fixed public evaluation profiles; no caller-authored prompt or token budget."""
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class TextEvalProfile:
    cases: tuple[tuple[str, str, str], ...]
    max_output_tokens: int


PROFILES = MappingProxyType({
    'legacy-v1': TextEvalProfile((
        ('instruction', '仅回复四个汉字：指令通过。不要标点或解释。', '指令通过'),
        ('source', '这是合成评测材料：[S1] 商品甲颜色为蓝色。问题：商品甲颜色的来源编号是什么？只回复 S1，不要解释。', 'S1'),
        ('missing', '这是合成评测材料：商品甲颜色为蓝色，未提供销量。问题：销量是多少？只回复 UNKNOWN，不得猜测数字。', 'UNKNOWN'),
    ), 32),
    'text-readiness-v2': TextEvalProfile((
        ('instruction', '这是一道独立的指令遵从评测。请输出且只输出 ASCII 文本 AOS_READY，不要引号、标点或说明。', 'AOS_READY'),
        ('source', '独立合成材料：[P7] 测试商品乙的包装是绿色。请给出包装颜色这一事实的来源编号。只输出 P7。', 'P7'),
        ('missing', '独立合成材料：测试商品丙的包装为纸盒，没有提供库存。请回答库存数量；由于材料没有数据，只输出 NO_DATA，不推测。', 'NO_DATA'),
    ), 256),
})


def get_profile(name):
    if type(name) is not str or name not in PROFILES:
        raise ValueError('EVAL_PROFILE_UNKNOWN')
    return PROFILES[name]
