from masterit.library.relocation import RelocationOutcome
from masterit.tags.tag_edits import TagOutcome


def format_relocation_summary(verb: str, outcomes: list[RelocationOutcome], skipped: int) -> str:
    failures = [outcome for outcome in outcomes if not outcome.succeeded]
    succeeded = len(outcomes) - len(failures)
    summary = f"{succeeded} {verb}, {skipped} skipped, {len(failures)} failed."
    if not failures:
        return summary
    return f"{summary} {failures[0].source.name}: {failures[0].error}"


def format_tag_summary(outcomes: list[TagOutcome]) -> str:
    failures = [outcome for outcome in outcomes if not outcome.succeeded]
    summary = f"{len(outcomes) - len(failures)} tagged, {len(failures)} failed."
    if not failures:
        return summary
    return f"{summary} {failures[0].path.name}: {failures[0].error}"
