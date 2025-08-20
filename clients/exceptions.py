from typing import Dict, Any


class APIError(Exception):
    pass


class QueueLimitExceededError(APIError):
    """Raised when the queue limit is exceeded."""
    pass


class GraphQLClientError(Exception):
    pass


class GraphQLError(GraphQLClientError):

    def __init__(self, errors: Dict[str, Any]):
        self.errors = errors
        super().__init__(f"GraphQL API returned errors: {errors}")
