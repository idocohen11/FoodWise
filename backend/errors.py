class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


class DatabaseError(Exception):
    """A safe boundary around connection, execution, and transaction failures."""
