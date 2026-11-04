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


class DailyLimitReachedError(XXTAgentError):
    """Raised when daily watch duration or task point count limit is reached for a course."""
    def __init__(self, course_name: str, message: str = "Daily limit reached", limit_type: str = "duration_or_tasks", details: dict = None):
        super().__init__(f"Course '{course_name}' daily limit reached: {message}", error_code="DAILY_LIMIT_REACHED", details=details)
        self.course_name = course_name
        self.limit_type = limit_type


class VideoNotFoundError(XXTAgentError):
    """Raised when video element cannot be found (possibly blocked by face verification or frame issues)."""
    def __init__(self, message: str = "Video element not found", details: dict = None):
        super().__init__(message, error_code="VIDEO_NOT_FOUND", details=details)


class BlockedByFaceVerificationError(XXTAgentError):
    """Raised when page is blocked by server-side face verification that cannot be bypassed automatically."""
    def __init__(self, message: str = "Page blocked by server-side face verification", details: dict = None):
        super().__init__(message, error_code="FACE_BLOCKED_SERVER_SIDE", details=details)

