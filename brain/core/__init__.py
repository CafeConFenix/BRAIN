__all__ = ["Brain"]


def __getattr__(name):
    # Brain is imported only on demand. This way modules and tools
    # can use brain.core.data_manager without creating circular
    # imports.
    if name == "Brain":
        from brain.core.brain import Brain

        return Brain

    raise AttributeError(f"module 'brain.core' has no attribute {name!r}")
