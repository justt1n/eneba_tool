from typing import Any, Dict, Optional


class APIError(Exception):
    pass


class QueueLimitExceededError(APIError):
    """Raised when the queue limit is exceeded."""
    pass


class GraphQLClientError(Exception):
    def __init__(
            self,
            message: str,
            *,
            status_code: Optional[int] = None,
            url: Optional[str] = None,
            operation: Optional[str] = None,
            response_body: Optional[str] = None
    ):
        self.status_code = status_code
        self.url = url
        self.operation = operation
        self.response_body = response_body
        super().__init__(message)


class GraphQLError(GraphQLClientError):

    def __init__(self, errors: Dict[str, Any]):
        self.errors = errors
        super().__init__(f"GraphQL API returned errors: {errors}")
