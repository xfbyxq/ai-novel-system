"""exceptions 模块."""

class NovelSystemError(Exception):
    """Base exception for novel system."""

    def __init__(self, message: str = "An error occurred"):
        """初始化方法."""
        self.message = message
        super().__init__(self.message)


class NotFoundError(NovelSystemError):
    """Resource not found."""

    def __init__(self, resource: str = "Resource", id: str = ""):
        """初始化方法."""
        super().__init__(f"{resource} not found: {id}")


class GenerationError(NovelSystemError):
    """Error during novel generation."""

    pass


class LLMError(NovelSystemError):
    """Error communicating with LLM API."""

    pass
