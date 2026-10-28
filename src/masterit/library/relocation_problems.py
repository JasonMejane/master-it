from enum import StrEnum


class RelocationProblem(StrEnum):
    EMPTY_NAME = "Name is empty"
    INVALID_NAME = 'Name starts with "." or contains / \\ : * ? " < > | or a control character'
    DUPLICATE_TARGET = "Several files would get this name"
    TARGET_EXISTS = "A file with this name already exists"
    MISSING_TITLE = "No title tag"
