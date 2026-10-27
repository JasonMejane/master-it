from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from masterit.tagging.metadata.track_metadata import (
    build_provider_search,
    has_all_details,
    is_complete,
    merge_metadata,
)
from masterit.tagging.metadata.types import (
    CoverProvider,
    ExistingTags,
    MetadataProvider,
    ProviderNeeds,
    ProviderServices,
    TrackMetadata,
    TrackSearch,
)
from masterit.tagging.web.errors import ServiceError


@dataclass(frozen=True)
class ChainState:
    metadata: TrackMetadata
    matched: bool
    has_existing_cover: bool
    replaces_cover: bool

    @property
    def keeps_existing_cover(self) -> bool:
        return self.has_existing_cover and not self.replaces_cover

    @property
    def needs_fallback_cover(self) -> bool:
        return not self.has_existing_cover and self.metadata.cover_data is None

    def get_needs(self) -> ProviderNeeds:
        needs_cover = not self.keeps_existing_cover and self.metadata.cover_data is None
        return ProviderNeeds(cover=needs_cover, details=not has_all_details(self.metadata))


# Another service may still answer a failed one; any other error is a bug that fails the file.
def call_service[Result](run: Callable[[], Result | None]) -> Result | None:
    try:
        return run()
    except ServiceError:
        return None


def make_initial_state(existing: ExistingTags, replace_cover: bool) -> ChainState:
    metadata = TrackMetadata(existing.info, existing.extras)
    return ChainState(metadata, False, existing.has_cover, replace_cover)


def merge_candidate(state: ChainState, candidate: TrackMetadata | None) -> ChainState:
    if candidate is None:
        return state
    return replace(state, metadata=merge_metadata(state.metadata, candidate), matched=True)


class MetadataChain:
    def __init__(
        self,
        providers: Sequence[MetadataProvider],
        cover_providers: Sequence[CoverProvider],
        services: ProviderServices,
    ) -> None:
        self._providers = providers
        self._cover_providers = cover_providers
        self._services = services

    def clear_cache(self) -> None:
        self._services.images.clear()
        self._services.cache.clear()

    # replace_cover asks services for a cover even when the file has one, but no fallback.
    def find(
        self, search: TrackSearch, existing: ExistingTags, replace_cover: bool = False
    ) -> TrackMetadata | None:
        state = self._collect_metadata(search, make_initial_state(existing, replace_cover))
        if not state.matched:
            return None
        return self._add_fallback_cover(search, state).metadata

    def _collect_metadata(self, search: TrackSearch, state: ChainState) -> ChainState:
        for provider in self._providers:
            state = self._apply_provider(provider, search, state)
        return state

    def _add_fallback_cover(self, search: TrackSearch, state: ChainState) -> ChainState:
        for cover_provider in self._cover_providers:
            state = self._apply_cover_provider(cover_provider, search, state)
        return state

    def _apply_provider(
        self, provider: MetadataProvider, search: TrackSearch, state: ChainState
    ) -> ChainState:
        if is_complete(state.metadata, state.keeps_existing_cover):
            return state
        provider_search = build_provider_search(search, state.metadata.info)
        needs = state.get_needs()
        return merge_candidate(
            state, call_service(lambda: provider.find_metadata(provider_search, needs))
        )

    def _apply_cover_provider(
        self, cover_provider: CoverProvider, search: TrackSearch, state: ChainState
    ) -> ChainState:
        if not state.needs_fallback_cover:
            return state
        cover_search = build_provider_search(search, state.metadata.info)
        cover = call_service(lambda: cover_provider.find_cover(cover_search))
        return replace(state, metadata=replace(state.metadata, cover_data=cover))
