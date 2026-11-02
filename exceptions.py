# -*- coding: utf-8 -*-
"""Custom exceptions for Xuexitong Agent."""


class XXTAgentError(Exception):
    """Base exception for all XXTAgent errors."""
    def __init__(self, message: str, error_code: str = "GENERAL_ERROR", details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class AuthenticationError(XXTAgentError):
    """Raised when authentication (cookies/login) fails."""
    def __init__(self, message: str = "Authentication failed or session expired", details: dict = None):
        super().__init__(message, error_code="AUTHENTICATION_ERROR", details=details)


class CourseNotFoundError(XXTAgentError):
    """Raised when the specified course cannot be found."""
    def __init__(self, course_name: str, details: dict = None):
        super().__init__(f"Course '{course_name}' not found", error_code="COURSE_NOT_FOUND", details=details)


class FaceVerificationRequiredError(XXTAgentError):
    """Raised when face verification popup appears and bypass fails."""
    def __init__(self, message: str = "Face verification required and could not be bypassed", details: dict = None):
        super().__init__(message, error_code="FACE_VERIFICATION_REQUIRED", details=details)


class SolverError(XXTAgentError):
    """Raised when AI solver fails to answer questions."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, error_code="SOLVER_ERROR", details=details)


class BrowserError(XXTAgentError):
    """Raised when browser automation encounters fatal issue."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message, error_code="BROWSER_ERROR", details=details)
