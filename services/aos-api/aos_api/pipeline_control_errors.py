"""Closed control failures that may cross the pipeline result boundary."""
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


class SourceCallBudgetExhausted(RuntimeConflict):
    """The current approved source call count has already been consumed."""
