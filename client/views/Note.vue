<template>
  <ConfirmModal
    v-model="isDeleteModalVisible"
    title="Delete Note"
    :message="`Are you sure you want to delete the note '${note.title}'?`"
    confirmButtonText="Delete"
    confirmButtonStyle="danger"
    @confirm="deleteConfirmedHandler"
  />

  <ConfirmModal
    v-model="isSaveChangesModalVisible"
    title="Save Changes"
    message="Do you want to save your changes?"
    confirmButtonText="Save"
    confirmButtonStyle="success"
    rejectButtonText="Discard"
    rejectButtonStyle="danger"
    @confirm="saveHandler(true)"
    @reject="discardChanges"
  />

  <ConfirmModal
    v-model="isDraftModalVisible"
    title="Draft Detected"
    message="There is an unsaved draft of this note stored in this browser. Do you want to resume the draft version or delete it?"
    confirmButtonText="Resume Draft"
    confirmButtonStyle="cta"
    rejectButtonText="Delete Draft"
    rejectButtonStyle="danger"
    @confirm="setEditMode()"
    @reject="
      clearDraft();
      setEditMode();
    "
  />

  <ConfirmModal
    v-model="isDeleteTagModalVisible"
    title="Delete Tag"
    :message="`Delete the tag '${tagPendingDelete?.label}' from the whole application?`"
    confirmButtonText="Delete Tag"
    confirmButtonStyle="danger"
    @confirm="deleteTagConfirmedHandler"
  />

  <ConfirmModal
    v-model="isImportReplaceModalVisible"
    title="Replace Draft"
    message="Importing a file will replace the current title and content. Do you want to continue?"
    confirmButtonText="Replace"
    confirmButtonStyle="cta"
    rejectButtonText="Cancel"
    rejectButtonStyle="secondary"
    @confirm="confirmImportReplaceHandler"
    @reject="clearPendingImport"
  />

  <LoadingIndicator ref="loadingIndicator" class="flex h-full flex-col">
    <input
      ref="noteImportInput"
      type="file"
      :accept="noteImportAccept"
      class="hidden"
      @change="noteImportChangeHandler"
    />

    <div class="page-shell-note">
      <section class="app-surface app-hero">
        <div class="relative z-10 flex flex-col gap-6">
          <div class="min-w-0 flex-1">
            <div class="note-header-row">
              <p class="app-kicker mb-0">{{ noteKicker }}</p>

              <div class="note-header-actions print:hidden">
                <div v-if="canModify" class="note-edit-toggle">
                  <Toggle
                    label="Edit"
                    :isOn="editMode"
                    @click="toggleEditModeHandler"
                  />
                </div>

                <div v-if="editMode && canModify" class="note-save-action">
                  <CustomButton
                    v-if="isNewNote"
                    label="Upload"
                    :iconPath="mdiUpload"
                    @click="openImportDialog"
                  />
                  <CustomButton
                    label="Save"
                    :iconPath="mdilContentSave"
                    style="success"
                    @click="saveHandler(false)"
                    class="relative"
                  >
                    <div
                      v-show="unsavedChanges"
                      class="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-theme-brand"
                    ></div>
                  </CustomButton>
                </div>

                <div
                  v-if="showFavoriteButton || !isNewNote"
                  class="note-action-icons"
                  :class="{ 'border-l border-theme-border/70 pl-4': canModify }"
                >
                  <CustomButton
                    v-if="showFavoriteButton"
                    :iconPath="note.favorite ? mdiStar : mdiStarOutline"
                    :label="note.favorite ? 'Unfavorite' : 'Favorite'"
                    iconOnly
                    @click="toggleFavoriteHandler"
                  />
                  <CustomButton
                    v-if="!isNewNote"
                    :iconPath="mdiShareVariantOutline"
                    label="Share"
                    iconOnly
                    @click="shareHandler"
                  />
                  <CustomButton
                    v-if="!isNewNote"
                    :iconPath="mdiDownload"
                    label="Export"
                    iconOnly
                    @click="downloadHandler"
                  />
                  <CustomButton
                    v-if="canModify && !isNewNote"
                    :iconPath="mdiContentCopy"
                    label="Duplicate"
                    iconOnly
                    @click="duplicateHandler"
                  />
                  <CustomButton
                    v-show="canModify && !isNewNote"
                    :iconPath="mdilDelete"
                    label="Delete"
                    iconOnly
                    style="danger"
                    @click="deleteHandler"
                  />
                </div>
              </div>
            </div>

            <div class="max-w-4xl">
              <div
                class="break-words text-[2rem] font-semibold text-theme-text sm:text-[2.75rem]"
              >
                <span v-show="!editMode" :title="note.title">{{ note.title }}</span>
                <input
                  v-show="editMode"
                  v-model.trim="newTitle"
                  class="w-full bg-transparent text-theme-text outline-none placeholder:text-theme-text-very-muted"
                  placeholder="Title"
                />
              </div>

              <div
                v-if="visibleTags.length > 0 || editMode"
                class="mt-4 flex flex-wrap gap-2"
              >
                <Tag
                  v-for="tag in visibleTags"
                  :key="tag.id"
                  :tag="tag"
                />
              </div>

              <div class="mt-5 flex flex-wrap gap-2">
                <span v-if="note.groupName" class="meta-pill">
                  {{ note.groupName }}
                </span>
                <span v-if="!isNewNote" class="meta-pill">
                  {{ note.favorite ? "Favorite" : "Standard" }}
                </span>
                <span v-if="note.createdAt" class="meta-pill">
                  Created {{ note.createdAtAsString }}
                </span>
                <span v-if="note.lastModified" class="meta-pill">
                  Updated {{ note.lastModifiedAsString }}
                </span>
                <span v-if="visibleTags.length > 0" class="meta-pill">
                  {{ visibleTags.length }} tags
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        v-if="editMode"
        class="app-surface-muted rounded-[28px] px-5 py-5 sm:px-6"
      >
          <div class="flex flex-col gap-5">
          <div class="flex items-center justify-between gap-3">
            <p class="section-heading">Tags</p>
            <span class="meta-pill">
              {{ totalAssignedTagCount }}/{{ maxNoteTags }}
            </span>
          </div>

          <div v-if="availableTags.length > 0" class="flex flex-wrap gap-2">
            <Tag
              v-for="tag in availableTags"
              :key="tag.id"
              :tag="tag"
              clickable
              deletable
              :selected="selectedTagIds.includes(tag.id)"
              @click="toggleTagSelection(tag.id)"
              @delete="requestDeleteTag(tag)"
            />
          </div>

          <p v-else class="text-sm leading-7 text-theme-text-muted">
            No tags yet. Create one below to use it across the app.
          </p>

          <div
            class="rounded-[24px] border border-theme-border/70 bg-theme-background/20 p-4"
          >
            <div class="flex flex-col gap-4 xl:flex-row xl:items-end">
              <div class="min-w-0 flex-1">
                <div
                  class="flex min-h-[56px] flex-wrap items-center gap-2 rounded-[22px] border border-theme-border/70 bg-theme-panel/70 px-3 py-3"
                >
                  <input
                    v-model.trim="newTagLabel"
                    class="min-w-[150px] flex-1 bg-transparent text-sm text-theme-text outline-none placeholder:text-theme-text-very-muted"
                    placeholder="New tag label"
                    @keydown.enter.prevent="createTagHandler"
                  />
                  <CustomButton
                    :iconPath="mdiPlus"
                    label="Add tag"
                    iconOnly
                    size="sm"
                    @click="createTagHandler"
                  />
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2">
                <button
                  v-for="color in sessionTagColorPalette"
                  :key="color"
                  type="button"
                  class="palette-swatch"
                  :class="{
                    'border-theme-text': newTagColor === color,
                    'border-transparent': newTagColor !== color,
                  }"
                  :style="{ backgroundColor: color }"
                  @click="selectTagColor(color)"
                ></button>
                <Popover align="left" side="top" panelClass="palette-popover">
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
                            @change="rememberSessionTagColor(newTagColor)"
                          />
                          Choose custom color
                        </label>
                      </div>
                    </div>
                  </template>
                </Popover>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="app-surface document-shell flex-1">
        <div
          class="rounded-[24px] border border-theme-border/70 bg-theme-background/20"
        >
          <ToastViewer
            v-if="!editMode"
            :initialValue="note.content"
            :group="currentGroupQuery"
            class="toast-viewer px-4 py-4 sm:px-5 sm:py-5"
          />
          <div v-if="editMode" class="overflow-visible px-2 py-2 sm:px-3 sm:py-3">
            <ToastEditor
              ref="toastEditor"
              :initialValue="getInitialEditorValue()"
              :initialEditType="loadDefaultEditorMode()"
              :addImageBlobHook="addImageBlobHook"
              height="65vh"
              @change="startContentChangedTimeout"
              @keydown="keydownHandler"
            />
          </div>
        </div>
      </section>
    </div>
  </LoadingIndicator>
</template>

<style>
.toast-viewer li.task-list-item {
  pointer-events: none;
}

.toast-viewer li.task-list-item a {
  pointer-events: auto;
}
</style>

<script setup>
import {
  mdiContentCopy,
  mdiDownload,
  mdiNoteOffOutline,
  mdiPlus,
  mdiShareVariantOutline,
  mdiStar,
  mdiStarOutline,
  mdiUpload,
} from "@mdi/js";
import { mdilContentSave, mdilDelete } from "@mdi/light-js";
import Mousetrap from "mousetrap";
import { useToast } from "primevue/usetoast";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  apiErrorHandler,
  createAttachment,
  createNote,
  createTag,
  deleteNote,
  deleteTag,
  duplicateNote,
  getNote,
  getNoteExportUrl,
  getTags,
  updateNote,
} from "../api.js";
import { Note } from "../classes.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import CustomButton from "../components/CustomButton.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import Popover from "../components/Popover.vue";
import Tag from "../components/Tag.vue";
import Toggle from "../components/Toggle.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import { authTypes, maxNoteTags, tagColorPalette } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import {
  buildAppUrl,
  copyTextToClipboard,
  getToastOptions,
} from "../helpers.js";
import {
  getImportedNoteTitle,
  isSupportedNoteImportFile,
  noteImportAccept,
  noteImportMaxBytes,
} from "../noteImport.js";
import {
  cleanNoteTitleForRoute,
  groupQueryValue,
  withGroupQuery,
} from "../routeHelpers.js";
import { isCurrentTokenStored } from "../tokenStorage.js";

const props = defineProps({
  title: String,
  group: {
    type: String,
    default: undefined,
  },
});

const globalStore = useGlobalStore();
const availableTags = ref([]);
let contentChangedTimeout = null;
const editMode = ref(false);
const isDeleteModalVisible = ref(false);
const isDeleteTagModalVisible = ref(false);
const isDraftModalVisible = ref(false);
const isCreatingTag = ref(false);
const isImportReplaceModalVisible = ref(false);
const isSaveChangesModalVisible = ref(false);
const isNewNote = computed(() => !props.title);
const loadingIndicator = ref();
const newTagColor = ref(tagColorPalette[0]);
const newTagLabel = ref("");
const newTitle = ref("");
const note = ref(new Note());
const noteImportInput = ref();
const pendingImportFile = ref(null);
const reservedFilenameCharacters = /[<>:"/\\|?*]/;
const router = useRouter();
const selectedTagIds = ref([]);
const sessionTagColorPalette = ref([...tagColorPalette]);
const tagPendingDelete = ref(null);
const toast = useToast();
const toastEditor = ref();
const unsavedChanges = ref(false);

const canModify = computed(
  () =>
    Boolean(globalStore.config?.authType) &&
    globalStore.config.authType != authTypes.readOnly,
);
const currentGroupQuery = computed(() => {
  return (
    props.group ||
    globalStore.currentGroup ||
    globalStore.config?.defaultGroupId ||
    (globalStore.principal?.isAdmin ? "legacy" : undefined) ||
    undefined
  );
});
const showFavoriteButton = computed(() => canModify.value && !isNewNote.value);
const noteKicker = computed(() => {
  if (isNewNote.value) {
    return "New note";
  }

  if (editMode.value) {
    return "Editing note";
  }

  return note.value.favorite ? "Favorite note" : "Document";
});
const totalAssignedTagCount = computed(() => selectedTagIds.value.length);
const visibleTags = computed(() => {
  if (editMode.value) {
    return selectedTagIds.value
      .map((tagId) => availableTags.value.find((tag) => tag.id === tagId))
      .filter(Boolean);
  }

  return note.value.tags;
});

function sortTags(tags) {
  return [...tags].sort((a, b) => a.label.localeCompare(b.label));
}

function normalizeTagLabel(label) {
  return label.trim().toLowerCase();
}

function findTagByLabel(label) {
  const normalizedLabel = normalizeTagLabel(label);
  return availableTags.value.find(
    (tag) => normalizeTagLabel(tag.label) === normalizedLabel,
  );
}

async function refreshAvailableTags() {
  const data = await getTags(currentGroupQuery.value);
  availableTags.value = sortTags(data);
  return data;
}

function init() {
  const loadedGroupValue =
    note.value.groupId ||
    (note.value.groupName === "My notes" ? "legacy" : undefined);
  if (
    props.title &&
    props.title == note.value.title &&
    loadedGroupValue === currentGroupQuery.value
  ) {
    return;
  }

  if (currentGroupQuery.value) {
    globalStore.currentGroup = currentGroupQuery.value;
  }

  loadingIndicator.value.setLoading();
  newTagLabel.value = "";
  if (props.title) {
    getNote(props.title, currentGroupQuery.value)
      .then((data) => {
        note.value = data;
        const resolvedGroup =
          data.groupId ||
          (data.groupName === "My notes"
            ? "legacy"
            : currentGroupQuery.value || null);
        globalStore.currentGroup = resolvedGroup;
        selectedTagIds.value = note.value.tags.map((tag) => tag.id);
        return refreshAvailableTags().then(() => resolvedGroup);
      })
      .then(() => {
        loadingIndicator.value.setLoaded();
      })
      .catch((error) => {
        if (error.response?.status === 404) {
          loadingIndicator.value.setFailed("Note not found", mdiNoteOffOutline);
        } else {
          loadingIndicator.value.setFailed();
          apiErrorHandler(error, toast);
        }
      });
  } else {
    newTitle.value = "";
    selectedTagIds.value = [];
    note.value = new Note({
      title: "",
      content: "",
      favorite: false,
      tags: [],
    });
    editMode.value = false;
    nextTick(() => {
      editHandler();
      loadingIndicator.value.setLoaded();
    });
  }
}

function loadTags() {
  refreshAvailableTags().catch((error) => {
    apiErrorHandler(error, toast);
  });
}

function toggleEditModeHandler() {
  if (editMode.value) {
    closeHandler();
  } else {
    editHandler();
  }
}

function openImportDialog() {
  noteImportInput.value?.click();
}

function hasDraftContentForImportReplace() {
  const currentMarkdown = toastEditor.value?.getMarkdown() || "";
  return Boolean(newTitle.value.trim() || currentMarkdown.trim());
}

function clearPendingImport() {
  pendingImportFile.value = null;
  if (noteImportInput.value) {
    noteImportInput.value.value = "";
  }
}

async function importFileIntoDraft(file) {
  const importedContent = await file.text();
  const importedTitle = getImportedNoteTitle(file.name);

  newTitle.value = importedTitle;
  toastEditor.value?.setMarkdown(importedContent);
  unsavedChanges.value = true;
  setBeforeUnloadConfirmation(true);
  await nextTick();
  saveDraft();
  toast.add(
    getToastOptions("Note imported into the draft.", "Success", "success"),
  );
}

async function noteImportChangeHandler(event) {
  const [file] = Array.from(event.target?.files || []);
  if (!file) {
    clearPendingImport();
    return;
  }

  if (!isSupportedNoteImportFile(file)) {
    toast.add(
      getToastOptions(
        "Only .md, .markdown, and .txt files can be imported as notes.",
        "Unsupported File",
        "error",
      ),
    );
    clearPendingImport();
    return;
  }

  if (file.size > noteImportMaxBytes) {
    toast.add(
      getToastOptions(
        "The selected file is too large to import as a note.",
        "File Too Large",
        "error",
      ),
    );
    clearPendingImport();
    return;
  }

  if (hasDraftContentForImportReplace()) {
    pendingImportFile.value = file;
    isImportReplaceModalVisible.value = true;
    return;
  }

  try {
    await importFileIntoDraft(file);
  } catch (error) {
    console.error(error);
    toast.add(
      getToastOptions(
        "Unable to read the selected file.",
        "Import Failed",
        "error",
      ),
    );
  } finally {
    clearPendingImport();
  }
}

async function confirmImportReplaceHandler() {
  if (!pendingImportFile.value) {
    clearPendingImport();
    return;
  }

  try {
    await importFileIntoDraft(pendingImportFile.value);
  } catch (error) {
    console.error(error);
    toast.add(
      getToastOptions(
        "Unable to read the selected file.",
        "Import Failed",
        "error",
      ),
    );
  } finally {
    clearPendingImport();
  }
}

function editHandler() {
  const draftContent = loadDraft();
  if (draftContent) {
    isDraftModalVisible.value = true;
  } else {
    setEditMode();
  }
}

function setEditMode() {
  newTitle.value = note.value.title;
  selectedTagIds.value = note.value.tags.map((tag) => tag.id);
  newTagLabel.value = "";
  resetSessionTagColorPalette();
  unsavedChanges.value = false;
  editMode.value = true;
}

function getInitialEditorValue() {
  const draftContent = loadDraft();
  return draftContent ? draftContent : note.value.content;
}

function deleteHandler() {
  isDeleteModalVisible.value = true;
}

function deleteConfirmedHandler() {
  deleteNote(note.value.title, currentGroupQuery.value)
    .then(() => {
      toast.add(getToastOptions("Note deleted.", "Success", "success"));
      router.push({ name: "home", query: homeQuery() });
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function toggleFavoriteHandler() {
  updateNote(
    note.value.title,
    {
      favorite: !note.value.favorite,
    },
    currentGroupQuery.value,
  )
    .then((data) => {
      note.value = data;
      selectedTagIds.value = note.value.tags.map((tag) => tag.id);
      toast.add(getToastOptions("Favorite updated.", "Success", "success"));
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function duplicateHandler() {
  duplicateNote(note.value.title, currentGroupQuery.value)
    .then((data) => {
      toast.add(
        getToastOptions(
          `Created duplicate '${data.title}'.`,
          "Success",
          "success",
        ),
      );
      router.push({
        name: "note",
        params: { title: cleanNoteTitleForRoute(data.title) },
        query: noteQuery(data.title, data.groupId || currentGroupQuery.value)
          .query,
      });
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

function downloadHandler() {
  window.location.assign(
    getNoteExportUrl(note.value.title, groupQueryValue(currentGroupQuery.value)),
  );
}

function shareHandler() {
  const noteUrl = buildAppUrl(
    router.resolve({
      name: "note",
      params: { title: cleanNoteTitleForRoute(note.value.title) },
      query: noteQuery(note.value.title).query,
    }).href,
  );
  copyTextToClipboard(noteUrl)
    .then(() => {
      toast.add(getToastOptions("Share link copied.", "Success", "success"));
    })
    .catch(() => {
      toast.add(
        getToastOptions(
          "Unable to copy the share link in this browser.",
          "Copy Failed",
          "error",
        ),
      );
    });
}

function requestDeleteTag(tag) {
  tagPendingDelete.value = tag;
  isDeleteTagModalVisible.value = true;
}

function deleteTagConfirmedHandler() {
  if (!tagPendingDelete.value) {
    return;
  }

  deleteTag(tagPendingDelete.value.id, currentGroupQuery.value)
    .then(() => {
      availableTags.value = availableTags.value.filter(
        (tag) => tag.id !== tagPendingDelete.value.id,
      );
      selectedTagIds.value = selectedTagIds.value.filter(
        (tagId) => tagId !== tagPendingDelete.value.id,
      );
      note.value.tags = note.value.tags.filter(
        (tag) => tag.id !== tagPendingDelete.value.id,
      );
      toast.add(getToastOptions("Tag deleted.", "Success", "success"));
      tagPendingDelete.value = null;
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

async function saveHandler(close = false) {
  saveDefaultEditorMode();

  if (!newTitle.value) {
    toast.add(
      getToastOptions("Cannot save note without a title.", "Invalid", "error"),
    );
    return;
  }

  if (reservedFilenameCharacters.test(newTitle.value)) {
    badFilenameToast("Title");
    return;
  }

  if (selectedTagIds.value.length > maxNoteTags) {
    showTagLimitToast();
    return;
  }

  const newContent = toastEditor.value.getMarkdown();
  const resolvedTagIds = [...selectedTagIds.value];

  if (isNewNote.value) {
    await saveNew(newTitle.value, newContent, resolvedTagIds, close);
  } else {
    await saveExisting(newTitle.value, newContent, resolvedTagIds, close);
  }
}

async function saveNew(title, content, tagIds, close = false) {
  try {
    const data = await createNote(
      title,
      content,
      tagIds,
      currentGroupQuery.value,
    );
    clearDraft();
    note.value = data;
    await router.push({
      name: "note",
      params: { title: cleanNoteTitleForRoute(note.value.title) },
      query: noteQuery(note.value.title, data.groupId || currentGroupQuery.value)
        .query,
    });
    noteSaveSuccess(close);
  } catch (error) {
    noteSaveFailure(error);
  }
}

async function saveExisting(title, content, tagIds, close = false) {
  if (
    title == note.value.title &&
    content == note.value.content &&
    areTagSelectionsEqual(tagIds, note.value.tags.map((tag) => tag.id))
  ) {
    noteSaveSuccess(close);
    return;
  }

  try {
    const data = await updateNote(
      note.value.title,
      {
        newTitle: title,
        newContent: content,
        tagIds,
      },
      currentGroupQuery.value,
    );
    clearDraft();
    note.value = data;
    await router.replace(noteQuery(note.value.title, currentGroupQuery.value));
    noteSaveSuccess(close);
  } catch (error) {
    noteSaveFailure(error);
  }
}

function noteSaveFailure(error) {
  if (error.response?.status === 409) {
    toast.add(
      getToastOptions(
        "A note with this title already exists. Please try again with a new title.",
        "Duplicate",
        "error",
      ),
    );
  } else if (error.response?.status === 413) {
    entityTooLargeToast("note");
  } else {
    apiErrorHandler(error, toast);
  }
}

function noteSaveSuccess(close = false) {
  selectedTagIds.value = note.value.tags.map((tag) => tag.id);
  newTagLabel.value = "";
  unsavedChanges.value = false;
  if (close) {
    closeNote();
  } else {
    editMode.value = false;
  }
  setBeforeUnloadConfirmation(false);
  toast.add(getToastOptions("Note saved successfully.", "Success", "success"));
}

function closeHandler() {
  if (isContentChanged()) {
    isSaveChangesModalVisible.value = true;
  } else {
    closeNote();
  }
}

function discardChanges() {
  setBeforeUnloadConfirmation(false);
  closeNote();
}

function closeNote() {
  clearDraft();
  newTagLabel.value = "";
  resetSessionTagColorPalette();
  selectedTagIds.value = note.value.tags.map((tag) => tag.id);
  editMode.value = false;
  if (isNewNote.value) {
    router.push({ name: "home", query: homeQuery() });
  }
}

function addImageBlobHook(file, callback) {
  const altTextInputValue = document.getElementById(
    "toastuiAltTextInput",
  )?.value;

  postAttachment(file).then(function (data) {
    if (data) {
      const altText = altTextInputValue ? altTextInputValue : data.filename;
      callback(data.url, altText);
    }
  });
}

function postAttachment(file) {
  if (reservedFilenameCharacters.test(file.name)) {
    badFilenameToast("Attachment");
    return;
  }

  toast.add(getToastOptions("Uploading attachment..."));

  return createAttachment(file, currentGroupQuery.value)
    .then((data) => {
      toast.add(
        getToastOptions(
          "Attachment uploaded successfully.",
          "Success",
          "success",
        ),
      );
      return data;
    })
    .catch((error) => {
      if (error.response?.status === 409) {
        toast.add(
          getToastOptions(
            "An attachment with this filename already exists.",
            "Duplicate",
            "error",
          ),
        );
      } else if (error.response?.status == 413) {
        entityTooLargeToast("attachment");
      } else {
        apiErrorHandler(error, toast);
      }
    });
}

function startContentChangedTimeout() {
  clearContentChangedTimeout();
  contentChangedTimeout = setTimeout(contentChangedHandler, 1000);
}

function clearContentChangedTimeout() {
  if (contentChangedTimeout != null) {
    clearTimeout(contentChangedTimeout);
  }
}

function contentChangedHandler() {
  if (isContentChanged()) {
    unsavedChanges.value = true;
    setBeforeUnloadConfirmation(true);
    saveDraft();
  } else {
    unsavedChanges.value = false;
    setBeforeUnloadConfirmation(false);
    clearDraft();
  }
}

function draftStorageKey() {
  return note.value.title || "__new_note__";
}

function saveDraft() {
  const content = toastEditor.value?.getMarkdown() || "";
  const userHasPersistedToken = isCurrentTokenStored();
  if (content) {
    if (userHasPersistedToken) {
      localStorage.setItem(draftStorageKey(), content);
    } else {
      sessionStorage.setItem(draftStorageKey(), content);
    }
  }
}

function clearDraft() {
  localStorage.removeItem(draftStorageKey());
  sessionStorage.removeItem(draftStorageKey());
}

function loadDraft() {
  const localDraft = localStorage.getItem(draftStorageKey());
  const sessionDraft = sessionStorage.getItem(draftStorageKey());
  return localDraft || sessionDraft;
}

function showTagLimitToast() {
  toast.add(
    getToastOptions(
      `A note can have up to ${maxNoteTags} custom tags.`,
      "Tag Limit",
      "error",
    ),
  );
}

function toggleTagSelection(tagId) {
  if (selectedTagIds.value.includes(tagId)) {
    selectedTagIds.value = selectedTagIds.value.filter(
      (selectedTagId) => selectedTagId !== tagId,
    );
    return;
  }

  if (totalAssignedTagCount.value >= maxNoteTags) {
    showTagLimitToast();
    return;
  }

  selectedTagIds.value = [...selectedTagIds.value, tagId];
}

function selectTagColor(color) {
  newTagColor.value = color;
  rememberSessionTagColor(color);
}

function normalizeTagColor(color) {
  return String(color || "").trim().toUpperCase();
}

function resetSessionTagColorPalette() {
  sessionTagColorPalette.value = [...tagColorPalette];
  newTagColor.value = sessionTagColorPalette.value[0];
}

function rememberSessionTagColor(color) {
  const normalizedColor = normalizeTagColor(color);
  if (!normalizedColor) {
    return;
  }

  newTagColor.value = normalizedColor;
  if (!sessionTagColorPalette.value.includes(normalizedColor)) {
    sessionTagColorPalette.value = [
      ...sessionTagColorPalette.value,
      normalizedColor,
    ];
  }
}

async function createTagHandler() {
  const label = newTagLabel.value.trim();
  if (!label || isCreatingTag.value) {
    return;
  }

  const existingTag = findTagByLabel(label);
  if (existingTag) {
    if (!selectedTagIds.value.includes(existingTag.id)) {
      if (totalAssignedTagCount.value >= maxNoteTags) {
        showTagLimitToast();
        return;
      }
      selectedTagIds.value = [...selectedTagIds.value, existingTag.id];
    }
    newTagLabel.value = "";
    return;
  }

  if (totalAssignedTagCount.value >= maxNoteTags) {
    showTagLimitToast();
    return;
  }

  isCreatingTag.value = true;
  try {
    const createdTag = await createTag(
      label,
      newTagColor.value,
      currentGroupQuery.value,
    );
    availableTags.value = sortTags([...availableTags.value, createdTag]);
    selectedTagIds.value = [...selectedTagIds.value, createdTag.id];
    newTagLabel.value = "";
  } catch (error) {
    if (error.response?.status === 409) {
      const refreshedTags = await refreshAvailableTags();
      const refreshedTag = refreshedTags.find(
        (tag) => normalizeTagLabel(tag.label) === normalizeTagLabel(label),
      );
      if (refreshedTag) {
        if (!selectedTagIds.value.includes(refreshedTag.id)) {
          if (totalAssignedTagCount.value >= maxNoteTags) {
            showTagLimitToast();
            return;
          }
          selectedTagIds.value = [...selectedTagIds.value, refreshedTag.id];
        }
        newTagLabel.value = "";
        return;
      }
    }
    apiErrorHandler(error, toast);
  } finally {
    isCreatingTag.value = false;
  }
}

Mousetrap.bind("e", () => {
  if (editMode.value === false && canModify.value) {
    editHandler();
  }
});

function keydownHandler(event) {
  if ((event.ctrlKey || event.metaKey) && event.key == "Enter") {
    saveHandler(false);
  }
  if (event.key == "Escape") {
    closeHandler();
  }
}

function handleGlobalSaveShortcut(event) {
  if (
    editMode.value === false ||
    canModify.value === false ||
    isSaveChangesModalVisible.value ||
    isDeleteModalVisible.value ||
    isDeleteTagModalVisible.value ||
    isDraftModalVisible.value ||
    isImportReplaceModalVisible.value
  ) {
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    event.stopPropagation();
    saveHandler(false);
  }
}

function entityTooLargeToast(entityName) {
  toast.add(
    getToastOptions(
      `This ${entityName} is too large. Please try again with a smaller ${entityName} or adjust your server configuration.`,
      "Failure",
      "error",
    ),
  );
}

function badFilenameToast(entityName) {
  toast.add(
    getToastOptions(
      'Due to filename restrictions, the following characters are not allowed: <>:"/\\|?*',
      `Invalid ${entityName}`,
      "error",
    ),
  );
}

function setBeforeUnloadConfirmation(enable = true) {
  if (enable) {
    window.onbeforeunload = () => {
      return true;
    };
  } else {
    window.onbeforeunload = null;
  }
}

function saveDefaultEditorMode() {
  const isWysiwygMode = toastEditor.value.isWysiwygMode();
  localStorage.setItem(
    "defaultEditorMode",
    isWysiwygMode ? "wysiwyg" : "markdown",
  );
}

function loadDefaultEditorMode() {
  const defaultWysiwygMode = localStorage.getItem("defaultEditorMode");
  return defaultWysiwygMode || "markdown";
}

function areTagSelectionsEqual(first, second) {
  const firstSorted = [...first].sort();
  const secondSorted = [...second].sort();
  return JSON.stringify(firstSorted) === JSON.stringify(secondSorted);
}

function isContentChanged() {
  const currentMarkdown = toastEditor.value
    ? toastEditor.value.getMarkdown()
    : note.value.content;
  return (
    newTitle.value != note.value.title ||
    currentMarkdown != note.value.content ||
    areTagSelectionsEqual(
      selectedTagIds.value,
      note.value.tags.map((tag) => tag.id),
    ) === false
  );
}

function noteQuery(title, group = currentGroupQuery.value) {
  return {
    name: "note",
    params: { title: cleanNoteTitleForRoute(title) },
    query: withGroupQuery({}, group),
  };
}

function homeQuery() {
  return withGroupQuery({}, currentGroupQuery.value);
}

watch(
  () => [props.title, props.group],
  () => {
    loadTags();
    init();
  },
);
watch([newTitle, selectedTagIds], () => {
  if (editMode.value) {
    contentChangedHandler();
  }
});
onMounted(() => {
  window.addEventListener("keydown", handleGlobalSaveShortcut, true);
  loadTags();
  init();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleGlobalSaveShortcut, true);
});
</script>
