class LayerReferenceError(ValueError):
    def __init__(self, reference: str, message: str, candidates=None):
        super().__init__(message)
        self.reference = reference
        self.candidates = list(candidates or [])


class AmbiguousLayerReferenceError(LayerReferenceError):
    pass


class MissingLayerReferenceError(LayerReferenceError):
    pass


class ExecutionCancelledError(RuntimeError):
    pass
