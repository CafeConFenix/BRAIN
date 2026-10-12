__all__ = ["Brain"]


def __getattr__(nombre):
    # Brain se importa solo cuando se pide. Así los módulos y las
    # herramientas pueden usar brain.core.data_manager sin crear
    # importaciones circulares.
    if nombre == "Brain":
        from brain.core.brain import Brain

        return Brain

    raise AttributeError(f"module 'brain.core' has no attribute {nombre!r}")
