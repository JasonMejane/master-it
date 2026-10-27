# A failure of the remote service, as opposed to a bug: another service may still answer.
class ServiceError(Exception):
    pass


# A missing resource stays missing, unlike a failing or slow service.
class HttpStatusError(ServiceError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


# A slow answer may come in time when asked again, unlike an error.
class ServiceTimeoutError(ServiceError):
    def __init__(self) -> None:
        super().__init__("timed out")
