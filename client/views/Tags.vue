<template>
  <ConfirmModal
    v-model="isDeleteModalVisible"
    title="Delete Tag"
    :message="`Delete the tag '${tagPendingDelete?.label}' from this scope?`"
    confirmButtonText="Delete Tag"
    confirmButtonStyle="danger"
    @confirm="deleteTagConfirmedHandler"
  />

  <div class="page-shell">
    <section class="app-surface app-hero">
      <div class="relative z-10 flex flex-col gap-6">
        <div class="max-w-3xl">
          <p class="app-kicker">Tags</p>
          <h1 class="app-title app-title-home">Manage reusable tags</h1>
          <p class="app-subtitle">
            {{ subtitleText }}
          </p>
        </div>
      </div>
    </section>

    <LoadingIndicator ref="loadingIndicator">
      <div
        v-if="!isWritable"
        class="app-surface-muted rounded-[28px] px-6 py-10 text-center"
      >
        <p class="section-heading">Access denied</p>
        <h2 class="section-title">Writable access required</h2>
        <p class="mx-auto mt-3 max-w-xl text-sm leading-7 text-theme-text-muted">
          This page is only available when notes can be modified.
        </p>
      </div>

      <div
        v-else-if="!hasAvailableScopes"
        class="app-surface-muted rounded-[28px] px-6 py-10 text-center"
      >
        <p class="section-heading">No access</p>
        <h2 class="section-title">No available scopes</h2>
        <p class="mx-auto mt-3 max-w-xl text-sm leading-7 text-theme-text-muted">
          You do not have access to any tag scopes yet.
        </p>
      </div>

      <div v-else class="space-y-6">
        <div class="list-toolbar">
          <GroupScopeDropdown
            :model-value="activeGroup"
            :options="groupOptions"
            @update:model-value="updateGroup"
          />
          <span class="meta-pill">Scope: {{ currentScopeName }}</span>
          <span class="meta-pill">{{ tags.length }} tags</span>
        </div>

        <section
          v-if="isAllGroupsScope"
          class="app-surface-muted rounded-[28px] px-5 py-5 sm:px-6"
        >
          <p class="section-heading">Read-only</p>
          <h2 class="section-title">Choose a specific scope to edit tags</h2>
          <p class="mt-3 max-w-2xl text-sm leading-7 text-theme-text-muted">
            You are currently viewing aggregated tags from all groups. Switch to
            My notes or a specific group to create, rename, recolor, or delete tags.
          </p>
        </section>

        <section class="app-surface-muted rounded-[28px] px-5 py-5 sm:px-6">
          <div class="flex items-end justify-between gap-4">
            <div>
              <p class="section-heading">Create tag</p>
              <h2 class="section-title">New reusable tag</h2>
            </div>
            <p class="section-meta">{{ currentScopeName }}</p>
          </div>

          <div class="mt-5 flex flex-col gap-4 xl:flex-row xl:items-end">
            <div class="min-w-0 flex-1">
              <input
                v-model.trim="newTagLabel"
                type="text"
                class="w-full rounded-[20px] border border-theme-border bg-theme-panel/80 px-4 py-3 text-theme-text shadow-[0_10px_30px_rgb(var(--theme-shadow)/0.06)] placeholder:text-theme-text-very-muted focus:border-theme-brand/40 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="New tag label"
                :disabled="!canEditTags || isCreatingTag"
                @keydown.enter.prevent="createTagHandler"
              />
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <button
                v-for="color in createTagPalette"
                :key="color"
                type="button"
                class="palette-swatch"
                :class="{
                  'border-theme-text': newTagColor === color,
                  'border-transparent': newTagColor !== color,
                  'cursor-not-allowed opacity-50': !canEditTags,
                }"
                :style="{ backgroundColor: color }"
                :disabled="!canEditTags"
                @click="selectCreateTagColor(color)"
              ></button>

              <Popover
                v-if="canEditTags"
                align="left"
                side="top"
                panelClass="palette-popover"
              >
                <template #trigger>
                  <CustomButton
                    :iconPath="mdiPlus"
                    label="More colors"
                    iconOnly
                    size="sm"
                  />
                </template>

                <template #default>
                  <div class="space-y-3">
                    <p
                      class="text-[11px] font-semibold uppercase tracking-[0.24em] text-theme-text-very-muted"
                    >
                      Custom color
                    </p>
                    <div
                      class="rounded-[20px] border border-theme-border/70 bg-theme-background/30 p-3"
                    >
                      <div class="flex items-center gap-3">
                        <span
                          class="h-10 w-10 rounded-full border border-theme-border/70"
                          :style="{ backgroundColor: newTagColor }"
                        ></span>
                        <div class="min-w-0 flex-1">
                          <p class="truncate text-sm font-medium text-theme-text">
                            {{ newTagColor }}
                          </p>
                          <p class="text-xs text-theme-text-muted">
                            Pick any color for the next reusable tag.
                          </p>
                        </div>
                      </div>

                      <label class="palette-color-input mt-3 flex w-full">
                        <input
                          v-model="newTagColor"
                          type="color"
                          class="absolute inset-0 cursor-pointer opacity-0"
                          :disabled="!canEditTags"
                          @change="rememberCreateTagColor(newTagColor)"
                        />
                        Choose custom color
                      </label>
                    </div>
                  </div>
                </template>
              </Popover>
              <CustomButton
                v-else
                :iconPath="mdiPlus"
                label="More colors"
                iconOnly
                size="sm"
                :disabled="true"
              />

              <CustomButton
                label="Create Tag"
                style="cta"
                :disabled="!canEditTags || isCreatingTag || !newTagLabel.trim()"
                @click="createTagHandler"
              />
            </div>
          </div>
        </section>

        <section class="app-surface-muted rounded-[28px] px-5 py-5 sm:px-6">
          <div class="flex items-end justify-between gap-4">
            <div>
              <p class="section-heading">Reusable tags</p>
              <h2 class="section-title">Existing tags</h2>
            </div>
            <p class="section-meta">{{ tags.length }} tags</p>
          </div>

          <div
            v-if="tags.length === 0"
            class="mt-5 rounded-[24px] border border-theme-border/70 bg-theme-panel/60 px-6 py-8 text-center"
          >
            <p class="section-heading">Empty state</p>
            <h3 class="section-title text-[1.4rem]">No reusable tags yet</h3>
            <p class="mx-auto mt-3 max-w-xl text-sm leading-7 text-theme-text-muted">
              Create your first reusable tag for {{ currentScopeName }} to start
              tagging notes faster.
            </p>
          </div>

          <div v-else class="mt-6 space-y-3">
            <article
              v-for="tag in tags"
              :key="tag.id"
              class="rounded-[24px] border border-theme-border/70 bg-theme-panel/60 p-4"
            >
              <div class="flex flex-col gap-4">
                <div class="flex flex-wrap items-start justify-between gap-4">
                  <div class="min-w-0 flex-1 space-y-3">
                    <div class="flex flex-wrap items-center gap-2">
                      <Tag
                        :label="tagDrafts[tag.id]?.label || tag.label"
                        :color="tagDrafts[tag.id]?.color || tag.color"
                      />
                      <span class="meta-pill">{{ tag.usageCount }} notes</span>
                      <span class="meta-pill">{{ tag.id }}</span>
                    </div>

                    <input
                      v-model.trim="tagDrafts[tag.id].label"
                      type="text"
                      class="w-full rounded-[18px] border border-theme-border/70 bg-theme-background/20 px-3 py-2 text-sm text-theme-text focus:border-theme-brand/40 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                      placeholder="Tag label"
                      :disabled="!canEditTags"
                      @keydown.enter.prevent="saveTagHandler(tag)"
                    />
                  </div>

                  <div class="flex flex-wrap items-center gap-2">
                    <CustomButton
                      label="Save"
                      size="sm"
                      style="success"
                      :disabled="!canEditTags || !isTagDirty(tag)"
                      @click="saveTagHandler(tag)"
                    />
                    <CustomButton
                      label="Delete"
                      size="sm"
                      style="danger"
                      :disabled="!canEditTags"
                      @click="requestDeleteTag(tag)"
                    />
                  </div>
                </div>

                <div class="flex flex-wrap items-center gap-2">
                  <button
                    v-for="color in getRowPalette(tag.id)"
                    :key="color"
                    type="button"
                    class="palette-swatch"
                    :class="{
                      'border-theme-text': tagDrafts[tag.id].color === color,
                      'border-transparent': tagDrafts[tag.id].color !== color,
                      'cursor-not-allowed opacity-50': !canEditTags,
                    }"
                    :style="{ backgroundColor: color }"
                    :disabled="!canEditTags"
                    @click="selectRowTagColor(tag.id, color)"
                  ></button>

                  <Popover
                    v-if="canEditTags"
                    align="left"
                    side="top"
                    panelClass="palette-popover"
                  >
                    <template #trigger>
                      <CustomButton
                        :iconPath="mdiPlus"
                        label="More colors"
                        iconOnly
                        size="sm"
                      />
                    </template>

                    <template #default>
                      <div class="space-y-3">
                        <p
                          class="text-[11px] font-semibold uppercase tracking-[0.24em] text-theme-text-very-muted"
                        >
                          Custom color
                        </p>
                        <div
                          class="rounded-[20px] border border-theme-border/70 bg-theme-background/30 p-3"
                        >
                          <div class="flex items-center gap-3">
                            <span
                              class="h-10 w-10 rounded-full border border-theme-border/70"
                              :style="{ backgroundColor: tagDrafts[tag.id].color }"
                            ></span>
                            <div class="min-w-0 flex-1">
                              <p class="truncate text-sm font-medium text-theme-text">
                                {{ tagDrafts[tag.id].color }}
                              </p>
                              <p class="text-xs text-theme-text-muted">
                                Pick any color for this tag.
                              </p>
                            </div>
                          </div>

                          <label class="palette-color-input mt-3 flex w-full">
                            <input
                              v-model="tagDrafts[tag.id].color"
                              type="color"
                              class="absolute inset-0 cursor-pointer opacity-0"
                              :disabled="!canEditTags"
                              @change="rememberRowTagColor(tag.id, tagDrafts[tag.id].color)"
                            />
                            Choose custom color
                          </label>
                        </div>
                      </div>
                    </template>
                  </Popover>
                  <CustomButton
                    v-else
                    :iconPath="mdiPlus"
                    label="More colors"
                    iconOnly
                    size="sm"
                    :disabled="true"
                  />
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </LoadingIndicator>
  </div>
</template>

<script setup>
import { mdiPlus } from "@mdi/js";
import { useToast } from "primevue/usetoast";
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  apiErrorHandler,
  createTag,
  deleteTag,
  getTags,
  updateTag,
} from "../api.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import CustomButton from "../components/CustomButton.vue";
import GroupScopeDropdown from "../components/GroupScopeDropdown.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import Popover from "../components/Popover.vue";
import Tag from "../components/Tag.vue";
import { authTypes, tagColorPalette } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import { withGroupQuery } from "../routeHelpers.js";

const props = defineProps({
  group: {
    type: String,
    default: undefined,
  },
});

const globalStore = useGlobalStore();
const createTagPalette = ref([...tagColorPalette]);
const isCreatingTag = ref(false);
const isDeleteModalVisible = ref(false);
const isMounted = ref(false);
const loadingIndicator = ref();
const newTagColor = ref(tagColorPalette[0]);
const newTagLabel = ref("");
const rowColorPalettes = ref({});
const router = useRouter();
const tagDrafts = ref({});
const tagPendingDelete = ref(null);
const tags = ref([]);
const toast = useToast();
let loadRequestId = 0;

const configReady = computed(() => globalStore.config !== null);
const currentAuthType = computed(() => globalStore.config?.authType);
const isWritable = computed(
  () => Boolean(currentAuthType.value) && currentAuthType.value !== authTypes.readOnly,
);
const isAdmin = computed(() => globalStore.principal?.isAdmin === true);
const groupOptions = computed(() => {
  const options = [];
  if (isAdmin.value) {
    options.push({ id: "all", name: "All Groups" });
    options.push({ id: "legacy", name: "My notes" });
  }
  return [...options, ...(globalStore.config?.availableGroups || [])];
});
const activeGroup = computed(() => {
  return (
    props.group ||
    globalStore.currentGroup ||
    globalStore.config?.defaultGroupId ||
    (isAdmin.value ? "legacy" : undefined)
  );
});
const currentScopeName = computed(() => {
  const selected = groupOptions.value.find((option) => option.id === activeGroup.value);
  if (selected) {
    return selected.name;
  }
  if (activeGroup.value === "all") {
    return "All Groups";
  }
  return "Current scope";
});
const hasAvailableScopes = computed(() => groupOptions.value.length > 0);
const isAllGroupsScope = computed(() => activeGroup.value === "all");
const canEditTags = computed(
  () => isWritable.value && Boolean(activeGroup.value) && !isAllGroupsScope.value,
);
const subtitleText = computed(() => {
  if (isAllGroupsScope.value) {
    return "Choose a specific scope to edit tags.";
  }
  return "Create, rename, recolor, and remove reusable tags for this scope.";
});

function normalizeTagLabel(value) {
  return (value || "").trim();
}

function normalizeTagColor(value) {
  return String(value || "").trim().toUpperCase();
}

function uniquePalette(colors) {
  const seen = new Set();
  return colors
    .map((color) => normalizeTagColor(color))
    .filter((color) => {
      if (!color || seen.has(color)) {
        return false;
      }
      seen.add(color);
      return true;
    });
}

function sortTags(items) {
  return [...items].sort((a, b) => a.label.localeCompare(b.label));
}

function syncTagState(nextTags) {
  tags.value = sortTags(nextTags);
  tagDrafts.value = Object.fromEntries(
    tags.value.map((tag) => [
      tag.id,
      {
        label: tag.label,
        color: normalizeTagColor(tag.color),
      },
    ]),
  );
  rowColorPalettes.value = Object.fromEntries(
    tags.value.map((tag) => [
      tag.id,
      uniquePalette([...tagColorPalette, tag.color]),
    ]),
  );
}

function rememberCreateTagColor(color) {
  const normalizedColor = normalizeTagColor(color);
  if (!normalizedColor) {
    return;
  }
  newTagColor.value = normalizedColor;
  if (!createTagPalette.value.includes(normalizedColor)) {
    createTagPalette.value = [...createTagPalette.value, normalizedColor];
  }
}

function selectCreateTagColor(color) {
  rememberCreateTagColor(color);
}

function selectRowTagColor(tagId, color) {
  rememberRowTagColor(tagId, color);
}

function rememberRowTagColor(tagId, color) {
  const normalizedColor = normalizeTagColor(color);
  if (!normalizedColor || !tagDrafts.value[tagId]) {
    return;
  }
  tagDrafts.value[tagId].color = normalizedColor;
  const palette = rowColorPalettes.value[tagId] || [...tagColorPalette];
  if (!palette.includes(normalizedColor)) {
    rowColorPalettes.value = {
      ...rowColorPalettes.value,
      [tagId]: [...palette, normalizedColor],
    };
  }
}

function getRowPalette(tagId) {
  return rowColorPalettes.value[tagId] || tagColorPalette;
}

function isTagDirty(tag) {
  const draft = tagDrafts.value[tag.id];
  if (!draft) {
    return false;
  }
  return (
    normalizeTagLabel(draft.label) !== tag.label ||
    normalizeTagColor(draft.color) !== normalizeTagColor(tag.color)
  );
}

function addTagToState(tag) {
  tags.value = sortTags([...tags.value, tag]);
  tagDrafts.value = {
    ...tagDrafts.value,
    [tag.id]: {
      label: tag.label,
      color: normalizeTagColor(tag.color),
    },
  };
  rowColorPalettes.value = {
    ...rowColorPalettes.value,
    [tag.id]: uniquePalette([...tagColorPalette, tag.color]),
  };
}

function replaceTagInState(updatedTag) {
  tags.value = sortTags(
    tags.value.map((tag) => (tag.id === updatedTag.id ? updatedTag : tag)),
  );
  tagDrafts.value = {
    ...tagDrafts.value,
    [updatedTag.id]: {
      label: updatedTag.label,
      color: normalizeTagColor(updatedTag.color),
    },
  };
  rowColorPalettes.value = {
    ...rowColorPalettes.value,
    [updatedTag.id]: uniquePalette([
      ...(rowColorPalettes.value[updatedTag.id] || tagColorPalette),
      updatedTag.color,
    ]),
  };
}

function removeTagFromState(tagId) {
  tags.value = tags.value.filter((tag) => tag.id !== tagId);
  const nextDrafts = { ...tagDrafts.value };
  delete nextDrafts[tagId];
  tagDrafts.value = nextDrafts;
  const nextPalettes = { ...rowColorPalettes.value };
  delete nextPalettes[tagId];
  rowColorPalettes.value = nextPalettes;
}

async function loadData() {
  if (!configReady.value || !isWritable.value) {
    loadingIndicator.value?.setLoaded();
    return;
  }

  if (!activeGroup.value) {
    syncTagState([]);
    loadingIndicator.value?.setLoaded();
    return;
  }

  const requestId = ++loadRequestId;
  if (globalStore.currentGroup !== activeGroup.value) {
    globalStore.currentGroup = activeGroup.value;
  }
  loadingIndicator.value?.setLoading();

  try {
    const data = await getTags(activeGroup.value);
    if (requestId !== loadRequestId) {
      return;
    }
    syncTagState(data);
    loadingIndicator.value?.setLoaded();
  } catch (error) {
    if (requestId !== loadRequestId) {
      return;
    }
    loadingIndicator.value?.setFailed();
    apiErrorHandler(error, toast);
  }
}

function updateGroup(group) {
  globalStore.currentGroup = group || null;
  router.push({
    name: "tags",
    query: withGroupQuery({}, group, { allowAll: true }),
  });
}

async function createTagHandler() {
  if (!canEditTags.value) {
    return;
  }

  const label = normalizeTagLabel(newTagLabel.value);
  if (!label || isCreatingTag.value) {
    return;
  }

  isCreatingTag.value = true;
  try {
    const createdTag = await createTag(label, newTagColor.value, activeGroup.value);
    addTagToState(createdTag);
    newTagLabel.value = "";
    toast.add(getToastOptions("Tag created.", "Success", "success"));
  } catch (error) {
    apiErrorHandler(error, toast);
  } finally {
    isCreatingTag.value = false;
  }
}

async function saveTagHandler(tag) {
  if (!canEditTags.value || !isTagDirty(tag)) {
    return;
  }

  const draft = tagDrafts.value[tag.id];
  try {
    const updatedTag = await updateTag(
      tag.id,
      {
        label: normalizeTagLabel(draft.label),
        color: normalizeTagColor(draft.color),
      },
      activeGroup.value,
    );
    replaceTagInState(updatedTag);
    toast.add(getToastOptions("Tag updated.", "Success", "success"));
  } catch (error) {
    apiErrorHandler(error, toast);
  }
}

function requestDeleteTag(tag) {
  tagPendingDelete.value = tag;
  isDeleteModalVisible.value = true;
}

async function deleteTagConfirmedHandler() {
  if (!tagPendingDelete.value || !canEditTags.value) {
    return;
  }

  const tagId = tagPendingDelete.value.id;
  try {
    await deleteTag(tagId, activeGroup.value);
    removeTagFromState(tagId);
    toast.add(getToastOptions("Tag deleted.", "Success", "success"));
    tagPendingDelete.value = null;
  } catch (error) {
    apiErrorHandler(error, toast);
  }
}

watch(
  () => [
    configReady.value,
    currentAuthType.value,
    props.group,
    globalStore.currentGroup,
    globalStore.config?.defaultGroupId,
    globalStore.config?.availableGroups?.length,
    isAdmin.value,
  ],
  () => {
    if (!isMounted.value) {
      return;
    }
    loadData();
  },
);

onMounted(() => {
  isMounted.value = true;
  if (configReady.value) {
    loadData();
  }
});
</script>
