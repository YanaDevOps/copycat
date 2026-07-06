<template>
  <ConfirmModal
    v-model="isDeleteModalVisible"
    title="Delete Note"
    :message="`Are you sure you want to delete '${notePendingDelete?.title}'?`"
    confirmButtonText="Delete"
    confirmButtonStyle="danger"
    @confirm="deleteConfirmedHandler"
  />

  <div class="page-shell">
    <LoadingIndicator ref="loadingIndicator">
      <div class="notes-column space-y-6">
        <div class="list-toolbar">
          <GroupScopeDropdown
            :model-value="activeGroup"
            :options="groupOptions"
            @update:model-value="updateGroup"
          />
          <SortDropdown
            :sort="effectiveSort"
            :order="effectiveOrder"
            @select="updateSort"
          />
          <TagFilterDropdown
            :tags="availableTags"
            :model-value="props.tagIds"
            @update:model-value="updateTagFilters"
          />
        </div>

        <div
          v-if="notes.length === 0"
          class="app-surface-muted rounded-[28px] px-6 py-10 text-center"
        >
          <p class="section-heading">{{ emptyStateKicker }}</p>
          <h2 class="section-title">{{ emptyStateTitle }}</h2>
          <p class="mx-auto mt-3 max-w-xl text-sm leading-7 text-theme-text-muted">
            {{ emptyStateBody }}
          </p>
        </div>

        <template v-else>
          <section v-if="showPinnedSection" class="space-y-4">
            <div class="flex items-end justify-between gap-4">
              <div>
                <p class="section-heading">Pinned</p>
                <h2 class="section-title">Favorites</h2>
              </div>
              <p class="section-meta">{{ pinnedNotes.length }} notes</p>
            </div>

            <div class="favorites-rail-shell">
              <div class="favorites-rail">
                <div
                  v-for="note in favoriteRailNotes"
                  :key="note.uniqueKey"
                  class="note-link-shell note-link-shell-compact note-link-shell-rail cursor-pointer"
                >
                  <SearchResultCard
                    :result="note"
                    compact
                    :canModify="canModify"
                    :showGroup="activeGroup === 'all'"
                    :showContentHighlights="isSearchMode"
                    :availableTags="availableTags"
                    :allowQuickTagging="allowQuickTagging"
                    :maxVisibleTags="2"
                    @open="openNote(note)"
                    @toggleFavorite="toggleFavoriteHandler(note)"
                    @toggleTag="toggleTagHandler(note, $event)"
                    @duplicate="duplicateHandler(note)"
                    @export="downloadHandler(note)"
                    @delete="requestDelete(note)"
                  />
                </div>
              </div>

              <RouterLink
                v-if="showFavoritesOverlay"
                :to="favoritesRoute"
                class="favorites-rail-overlay"
              >
                <span class="favorites-rail-overlay-button">Open</span>
              </RouterLink>
            </div>
          </section>

          <section v-if="visibleTimelineGroups.length" class="space-y-6">
            <div class="flex items-end justify-between gap-4">
              <div>
                <p class="section-heading">{{ timelineHeading }}</p>
                <h2 class="section-title">{{ timelineTitle }}</h2>
              </div>
              <p class="section-meta">{{ timelineResults.length }} notes</p>
            </div>

            <div class="space-y-8">
              <div
                v-for="group in visibleTimelineGroups"
                :key="group.key"
                class="timeline-group"
              >
                <div class="timeline-label-shell">
                  <p class="timeline-label">{{ group.label }}</p>
                  <span class="timeline-count">{{ group.items.length }} notes</span>
                </div>

                <div class="timeline-stack">
                  <div
                    v-for="note in group.items"
                    :key="note.uniqueKey"
                    class="note-link-shell note-link-shell-compact cursor-pointer"
                    :class="{ 'note-link-shell-search': isSearchMode }"
                  >
                    <SearchResultCard
                      :result="note"
                      compact
                      :canModify="canModify"
                      :showGroup="activeGroup === 'all'"
                      :showContentHighlights="isSearchMode"
                      :availableTags="availableTags"
                      :allowQuickTagging="allowQuickTagging"
                      @open="openNote(note)"
                      @toggleFavorite="toggleFavoriteHandler(note)"
                      @toggleTag="toggleTagHandler(note, $event)"
                      @duplicate="duplicateHandler(note)"
                      @export="downloadHandler(note)"
                      @delete="requestDelete(note)"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div
              v-if="hasMoreTimelineResults"
              ref="loadMoreSentinel"
              class="h-0"
              aria-hidden="true"
            ></div>
          </section>
        </template>
      </div>
    </LoadingIndicator>
  </div>
</template>

<script setup>
import { useToast } from "primevue/usetoast";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRouter } from "vue-router";

import {
  apiErrorHandler,
  deleteNote,
  duplicateNote,
  getNoteExportUrl,
  getTags,
  searchNotes,
  updateNote,
} from "../api.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import GroupScopeDropdown from "../components/GroupScopeDropdown.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import SearchResultCard from "../components/SearchResultCard.vue";
import SortDropdown from "../components/SortDropdown.vue";
import TagFilterDropdown from "../components/TagFilterDropdown.vue";
import {
  authTypes,
  maxNoteTags,
  params,
  searchOrderOptions,
  searchSortOptions,
} from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions, groupNotesByMonth } from "../helpers.js";
import {
  groupQueryValue,
  noteRouteLocation,
  withGroupQuery,
} from "../routeHelpers.js";

const props = defineProps({
  searchTerm: {
    type: String,
    default: undefined,
  },
  sort: {
    type: String,
    default: undefined,
  },
  order: {
    type: String,
    default: undefined,
  },
  tagIds: {
    type: Array,
    default: () => [],
  },
  favoriteOnly: Boolean,
  group: {
    type: String,
    default: undefined,
  },
});

const globalStore = useGlobalStore();
const availableTags = ref([]);
const isMounted = ref(false);
const isDeleteModalVisible = ref(false);
const loadMoreSentinel = ref();
const loadingIndicator = ref();
const notePendingDelete = ref(null);
const notes = ref([]);
const renderedTimelineLimit = ref(60);
const router = useRouter();
const toast = useToast();
let listIntersectionObserver = null;
let refreshRequestId = 0;
const notesChangedEventName = "copycat:notes-changed";
const initialTimelineRenderLimit = 60;
const timelineRenderBatchSize = 40;

const configReady = computed(() => globalStore.config !== null);
const activeGroup = computed(() => {
  return (
    props.group ||
    globalStore.currentGroup ||
    globalStore.config?.defaultGroupId ||
    (globalStore.principal?.isAdmin ? "legacy" : undefined) ||
    undefined
  );
});
const groupOptions = computed(() => {
  const options = [];
  if (globalStore.principal?.isAdmin) {
    options.push({ id: "all", name: "All Groups" });
    options.push({ id: "legacy", name: "My notes" });
  }
  return [...options, ...(globalStore.config?.availableGroups || [])];
});
const currentAuthType = computed(() => globalStore.config?.authType);
const canModify = computed(
  () => Boolean(currentAuthType.value) && currentAuthType.value !== authTypes.readOnly,
);
const allowQuickTagging = computed(
  () => canModify.value && activeGroup.value !== "all",
);
const requestedSearchTerm = computed(() => props.searchTerm || "*");
const effectiveSort = computed(() => {
  if (props.sort) {
    return props.sort;
  }

  return requestedSearchTerm.value === "*"
    ? searchSortOptions.lastModified
    : searchSortOptions.score;
});
const effectiveOrder = computed(() => {
  if (props.order) {
    return props.order;
  }

  return effectiveSort.value === searchSortOptions.title
    ? searchOrderOptions.asc
    : searchOrderOptions.desc;
});
const isOverviewMode = computed(
  () =>
    !props.favoriteOnly &&
    !props.searchTerm &&
    !props.sort &&
    !props.order &&
    props.tagIds.length === 0,
);
const isFavoritesMode = computed(() => props.favoriteOnly);
const isSearchMode = computed(
  () => Boolean(props.searchTerm && props.searchTerm !== "*"),
);
const favoritesRoute = computed(() => ({
  name: "home",
  query: withGroupQuery(
    {
      [params.searchTerm]: "*",
      [params.sort]: searchSortOptions.lastModified,
      [params.order]: searchOrderOptions.desc,
      [params.favoriteOnly]: "true",
    },
    activeGroup.value,
    { allowAll: true },
  ),
}));
const favoriteNotes = computed(() => notes.value.filter((note) => note.favorite));
const pinnedNotes = computed(() =>
  isFavoritesMode.value ? [] : favoriteNotes.value,
);
const favoriteRailNotes = computed(() => {
  if (pinnedNotes.value.length <= 2) {
    return pinnedNotes.value;
  }
  return pinnedNotes.value.slice(0, 3);
});
const nonFavoriteNotes = computed(() =>
  notes.value.filter((note) => !note.favorite),
);
const timelineResults = computed(() => {
  if (isFavoritesMode.value) {
    return notes.value;
  }
  if (nonFavoriteNotes.value.length > 0) {
    return nonFavoriteNotes.value;
  }
  return notes.value;
});
const visibleTimelineResults = computed(() =>
  timelineResults.value.slice(0, renderedTimelineLimit.value),
);
const groupField = computed(() =>
  isOverviewMode.value || effectiveSort.value !== searchSortOptions.createdAt
    ? "lastModified"
    : "createdAt",
);
const visibleTimelineGroups = computed(() =>
  groupNotesByMonth(visibleTimelineResults.value, groupField.value),
);
const hasMoreTimelineResults = computed(
  () => renderedTimelineLimit.value < timelineResults.value.length,
);
const showPinnedSection = computed(() => pinnedNotes.value.length > 0);
const showFavoritesOverlay = computed(() => pinnedNotes.value.length > 2);
const timelineHeading = computed(() => {
  if (isFavoritesMode.value) {
    return "Pinned notes";
  }
  if (isSearchMode.value) {
    return "Search results";
  }
  return "Timeline";
});
const timelineTitle = computed(() => {
  if (isFavoritesMode.value) {
    return "Favorites by month";
  }
  if (isSearchMode.value) {
    return `Results for "${props.searchTerm}"`;
  }
  return "All notes";
});
const emptyStateKicker = computed(() => {
  if (isFavoritesMode.value) {
    return "Pinned notes";
  }
  if (isSearchMode.value) {
    return "Search results";
  }
  return "Getting started";
});
const emptyStateTitle = computed(() => {
  if (isFavoritesMode.value) {
    return "No favorites yet";
  }
  if (isSearchMode.value) {
    return "No results found";
  }
  return "No notes yet";
});
const emptyStateBody = computed(() => {
  if (isFavoritesMode.value) {
    return "Star notes to keep them in your pinned collection.";
  }
  if (isSearchMode.value) {
    return "Try a different search term or remove some filters.";
  }
  return "Create your first note to populate this workspace and start building your knowledge base.";
});

function noteGroupValue(note) {
  if (note.groupId) {
    return note.groupId;
  }
  if (note.groupName === "My notes") {
    return "legacy";
  }
  return activeGroup.value;
}

function syncTopBarCounts() {
  globalStore.topBarCounts = {
    notes: notes.value.length,
    favorites: favoriteNotes.value.length,
    customTags: availableTags.value.length,
  };
}

function resetRenderedTimelineLimit() {
  renderedTimelineLimit.value =
    typeof IntersectionObserver === "undefined"
      ? Number.MAX_SAFE_INTEGER
      : initialTimelineRenderLimit;
}

function showMoreTimelineResults() {
  renderedTimelineLimit.value = Math.min(
    renderedTimelineLimit.value + timelineRenderBatchSize,
    timelineResults.value.length,
  );
}

function setupListIntersectionObserver() {
  if (typeof IntersectionObserver === "undefined") {
    renderedTimelineLimit.value = Number.MAX_SAFE_INTEGER;
    return;
  }

  listIntersectionObserver?.disconnect();
  listIntersectionObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        showMoreTimelineResults();
      }
    },
    { rootMargin: "700px 0px" },
  );

  if (loadMoreSentinel.value) {
    listIntersectionObserver.observe(loadMoreSentinel.value);
  }
}

async function refreshHome() {
  if (!configReady.value) {
    return;
  }

  const requestId = ++refreshRequestId;
  const resolvedGroup = activeGroup.value || null;
  let tagError = null;

  if (globalStore.currentGroup !== resolvedGroup) {
    globalStore.currentGroup = resolvedGroup;
  }

  loadingIndicator.value?.setLoading();

  try {
    const [noteData, tagData] = await Promise.all([
      searchNotes({
        term: isOverviewMode.value ? "*" : requestedSearchTerm.value,
        sort: isOverviewMode.value
          ? searchSortOptions.lastModified
          : effectiveSort.value,
        order: isOverviewMode.value
          ? searchOrderOptions.desc
          : effectiveOrder.value,
        favoritesFirst: true,
        tagIds: isOverviewMode.value ? [] : props.tagIds,
        favoriteOnly: isOverviewMode.value ? false : props.favoriteOnly,
        group: resolvedGroup || undefined,
      }),
      getTags(resolvedGroup || undefined).catch((error) => {
        tagError = error;
        return [];
      }),
    ]);

    if (requestId !== refreshRequestId) {
      return;
    }

    notes.value = noteData;
    resetRenderedTimelineLimit();
    availableTags.value = tagData;
    syncTopBarCounts();
    loadingIndicator.value?.setLoaded();

    if (tagError) {
      apiErrorHandler(tagError, toast);
    }
  } catch (error) {
    if (requestId !== refreshRequestId) {
      return;
    }

    notes.value = [];
    resetRenderedTimelineLimit();
    availableTags.value = [];
    syncTopBarCounts();
    loadingIndicator.value?.setFailed();
    apiErrorHandler(error, toast);
  }
}

function buildHomeQuery({
  searchTerm = undefined,
  sort = undefined,
  order = undefined,
  tagIds = [],
  favoriteOnly = false,
  group = undefined,
}) {
  const query = {};

  if (searchTerm !== undefined) {
    query[params.searchTerm] = searchTerm;
  }
  if (sort) {
    query[params.sort] = sort;
  }
  if (order) {
    query[params.order] = order;
  }
  if (tagIds.length > 0) {
    query[params.tagIds] = tagIds.join(",");
  }
  if (favoriteOnly) {
    query[params.favoriteOnly] = "true";
  }
  return withGroupQuery(query, group, { allowAll: true });
}

function updateRoute(options) {
  router.push({
    name: "home",
    query: buildHomeQuery(options),
  });
}

function updateGroup(group) {
  globalStore.currentGroup = group;
  if (isOverviewMode.value) {
    router.push({
      name: "home",
      query: withGroupQuery({}, group, { allowAll: true }),
    });
    return;
  }

  updateRoute({
    searchTerm: requestedSearchTerm.value,
    sort: effectiveSort.value,
    order: effectiveOrder.value,
    tagIds: [],
    favoriteOnly: props.favoriteOnly,
    group,
  });
}

function updateSort(option) {
  updateRoute({
    searchTerm: requestedSearchTerm.value,
    sort: option.sort,
    order: option.order,
    tagIds: props.tagIds,
    favoriteOnly: props.favoriteOnly,
    group: activeGroup.value,
  });
}

function updateTagFilters(tagIds) {
  updateRoute({
    searchTerm: requestedSearchTerm.value,
    sort: effectiveSort.value,
    order: effectiveOrder.value,
    tagIds,
    favoriteOnly: props.favoriteOnly,
    group: activeGroup.value,
  });
}

function openNote(note) {
  const group = noteGroupValue(note);
  router.push(noteRouteLocation(note.title, group));
}

function patchNoteInList(updatedNote, previousTitle) {
  notes.value = notes.value.map((currentNote) => {
    if (
      currentNote.title === previousTitle &&
      noteGroupValue(currentNote) === noteGroupValue(updatedNote)
    ) {
      currentNote.title = updatedNote.title;
      currentNote.lastModified = updatedNote.lastModified;
      currentNote.createdAt = updatedNote.createdAt;
      currentNote.favorite = updatedNote.favorite;
      currentNote.tags = updatedNote.tags;
      currentNote.groupId = updatedNote.groupId ?? currentNote.groupId ?? null;
      currentNote.groupName =
        updatedNote.groupName ?? currentNote.groupName ?? null;
    }
    return currentNote;
  });
}

function toggleFavoriteHandler(note) {
  updateNote(
    note.title,
    {
      favorite: !note.favorite,
    },
    noteGroupValue(note),
  )
    .then(() => {
      toast.add(getToastOptions("Favorite updated.", "Success", "success"));
      refreshHome();
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function toggleTagHandler(note, tagId) {
  const currentTagIds = (note.tags || []).map((tag) => tag.id);
  const hasTag = currentTagIds.includes(tagId);
  const nextTagIds = hasTag
    ? currentTagIds.filter((currentTagId) => currentTagId !== tagId)
    : [...currentTagIds, tagId];

  if (!hasTag && currentTagIds.length >= maxNoteTags) {
    toast.add(
      getToastOptions(
        `A note can have up to ${maxNoteTags} custom tags.`,
        "Tag Limit",
        "error",
      ),
    );
    return;
  }

  updateNote(
    note.title,
    {
      tagIds: nextTagIds,
    },
    noteGroupValue(note),
  )
    .then((data) => {
      patchNoteInList(data, note.title);
      syncTopBarCounts();
      toast.add(getToastOptions("Tags updated.", "Success", "success"));
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function duplicateHandler(note) {
  duplicateNote(note.title, noteGroupValue(note))
    .then((data) => {
      toast.add(
        getToastOptions(
          `Created duplicate '${data.title}'.`,
          "Success",
          "success",
        ),
      );
      router.push(
        noteRouteLocation(data.title, data.groupId || noteGroupValue(note)),
      );
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function downloadHandler(note) {
  window.location.assign(
    getNoteExportUrl(note.title, groupQueryValue(noteGroupValue(note))),
  );
}

function requestDelete(note) {
  notePendingDelete.value = note;
  isDeleteModalVisible.value = true;
}

function deleteConfirmedHandler() {
  if (!notePendingDelete.value) {
    return;
  }

  deleteNote(
    notePendingDelete.value.title,
    noteGroupValue(notePendingDelete.value),
  )
    .then(() => {
      toast.add(getToastOptions("Note deleted.", "Success", "success"));
      notePendingDelete.value = null;
      refreshHome();
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

watch(
  () => [
    configReady.value,
    props.searchTerm,
    props.sort,
    props.order,
    props.favoriteOnly,
    props.tagIds.join(","),
    props.group,
    globalStore.config?.defaultGroupId,
    globalStore.principal?.isAdmin,
  ],
  () => {
    if (!configReady.value || !isMounted.value) {
      return;
    }
    refreshHome();
  },
);

watch(loadMoreSentinel, () => {
  if (!isMounted.value) {
    return;
  }
  setupListIntersectionObserver();
});

watch(hasMoreTimelineResults, () => {
  if (!isMounted.value) {
    return;
  }
  setupListIntersectionObserver();
});

onMounted(() => {
  window.addEventListener(notesChangedEventName, refreshHome);
  isMounted.value = true;
  setupListIntersectionObserver();
  if (configReady.value) {
    refreshHome();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener(notesChangedEventName, refreshHome);
  listIntersectionObserver?.disconnect();
  listIntersectionObserver = null;
});
</script>
