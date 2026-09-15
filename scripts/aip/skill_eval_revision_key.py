"""Keep historical Eval replay keys while separating new graph revisions."""
import re


def skill_eval_revision_key(legacy_key, graph):
    if graph.revision < 1 or not re.fullmatch(r'[0-9a-f]{64}',graph.graph_hash):
        raise ValueError('exact graph revision and hash required')
    if graph.revision == 1:
        return legacy_key
    return f'{legacy_key}-graph-r{graph.revision}-{graph.graph_hash}'
