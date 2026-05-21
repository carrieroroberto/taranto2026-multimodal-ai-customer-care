class AppServiceError(Exception):
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ValidationServiceError(AppServiceError):
    status_code = 422


class DependencyServiceError(AppServiceError):
    status_code = 503
