<template>
  <Modal
    v-model="isImportModalVisible"
    class="border-none"
    :closeHandlerOverride="closeImportModal"
  >
    <div class="p-6 sm:p-8">
      <p class="section-heading">
        {{ isImporting ? "Importing" : "Import Summary" }}
      </p>
      <h2 class="section-title">
        {{ isImporting ? "Import in progress" : importSummaryTitle }}
      </h2>
      <p class="mt-3 text-sm leading-7 text-theme-text-muted">
        {{ isImporting ? importProgressDescription : importSummaryDescription }}
      </p>

      <div v-if="isImporting" class="mt-6 space-y-3">
        <div class="h-2 overflow-hidden rounded-full bg-theme-background/40">
          <div
            class="h-full rounded-full bg-theme-brand transition-all duration-200"
            :style="{ width: `${importProgressPercent}%` }"
          ></div>
        </div>
        <p class="text-sm text-theme-text-muted">
          {{ importProgress.completedCount }}/{{ importProgress.totalCount }}
          completed
        </p>
      </div>

      <div v-else class="mt-6 grid gap-3 sm:grid-cols-3">
        <div class="app-surface-muted rounded-[24px] px-4 py-4">
          <p class="section-heading">Selected</p>
          <p class="mt-2 text-2xl font-semibold text-theme-text">
            {{ importSummary.totalSelected }}
          </p>
        </div>
        <div class="app-surface-muted rounded-[24px] px-4 py-4">
          <p class="section-heading">Imported</p>
          <p class="mt-2 text-2xl font-semibold text-theme-text">
            {{ importSummary.importedCount }}
          </p>
        </div>
        <div class="app-surface-muted rounded-[24px] px-4 py-4">
          <p class="section-heading">Renamed</p>
          <p class="mt-2 text-2xl font-semibold text-theme-text">
            {{ importSummary.renamedItems.length }}
          </p>
        </div>
      </div>

      <div
        v-if="!isImporting && (importSummary.renamedItems.length || importSummary.failedItems.length)"
        class="mt-6 space-y-4"
      >
        <div
          v-if="importSummary.renamedItems.length"
          class="rounded-[24px] border border-theme-border/70 bg-theme-background/20 p-4"
        >
          <p class="section-heading">Renamed</p>
          <div class="mt-3 max-h-48 space-y-2 overflow-auto">
            <div
              v-for="item in importSummary.renamedItems"
              :key="`${item.fileName}:${item.title}`"
              class="rounded-[18px] bg-theme-background/25 px-3 py-3"
            >
              <p class="text-sm font-medium text-theme-text">{{ item.fileName }}</p>
              <p class="mt-1 text-xs text-theme-text-muted">
                Saved as {{ item.title }}
              </p>
            </div>
          </div>
        </div>

        <div
          v-if="importSummary.failedItems.length"
          class="rounded-[24px] border border-theme-border/70 bg-theme-background/20 p-4"
        >
          <p class="section-heading">Skipped / Failed</p>
          <div class="mt-3 max-h-56 space-y-2 overflow-auto">
            <div
              v-for="item in importSummary.failedItems"
              :key="`${item.fileName}:${item.reason}`"
              class="rounded-[18px] bg-theme-background/25 px-3 py-3"
            >
              <p class="text-sm font-medium text-theme-text">{{ item.fileName }}</p>
              <p class="mt-1 text-xs text-theme-text-muted">
                {{ item.reason }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!isImporting" class="mt-6 flex justify-end">
        <CustomButton label="Close" @click="closeImportModal" />
      </div>
    </div>
  </Modal>

  <input
    ref="importInput"
    type="file"
    :accept="noteImportAccept"
    multiple
    class="hidden"
    @change="bulkImportChangeHandler"
  />

  <nav class="-mx-1 mb-6 sm:-mx-2 md:mb-10 lg:-mx-3 print:hidden">
    <div class="app-surface rounded-[28px] px-5 py-3 sm:px-6 lg:px-7">
      <div
        class="topbar-layout"
        :class="{ 'topbar-layout-simple': !showMetrics }"
      >
        <div class="topbar-left">
          <RouterLink :to="{ name: 'home' }" v-if="!hideLogo" class="shrink-0">
            <Logo responsive></Logo>
          </RouterLink>
          <div v-if="showMetrics" class="topbar-metrics">
            <span v-for="badge in metricBadges" :key="badge.label" class="topbar-badge">
              <span class="topbar-badge-label">{{ badge.label }}</span>
              <span class="topbar-badge-value">{{ badge.value }}</span>
            </span>
          </div>
        </div>
        <div v-if="showMetrics" class="topbar-search-shell">
          <div class="topbar-search">
            <SearchInput
              :initialSearchTerm="currentSearchTerm"
              placeholder="Search notes..."
            />
          </div>
        </div>
        <div class="topbar-actions">
          <CustomButton
            v-if="showSearchButton"
            :iconPath="mdilMagnify"
            label="Search"
            @click="emit('toggleSearchModal')"
          />
          <RouterLink v-if="showNewButton" :to="newNoteRoute">
            <CustomButton
              :iconPath="mdilPlusCircle"
              label="New Note"
              style="cta"
            />
          </RouterLink>
          <CustomButton :iconPath="mdilMenu" label="Menu" @click="toggleMenu" />
          <PrimeMenu ref="menu" :model="menuItems" :popup="true" />
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import {
  mdilLogout,
  mdilMenu,
  mdilMonitor,
  mdilNoteMultiple,
  mdilPlusCircle,
  mdilMagnify,
} from "@mdi/light-js";
import { mdiDownload, mdiStarOutline, mdiTagOutline, mdiUpload } from "@mdi/js";
import { computed, ref } from "vue";
import { useToast } from "primevue/usetoast";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { createNote, getAllNotesExportUrl, logout } from "../api.js";
import Modal from "../components/Modal.vue";
import CustomButton from "../components/CustomButton.vue";
import Logo from "../components/Logo.vue";
import PrimeMenu from "../components/PrimeMenu.vue";
import SearchInput from "./SearchInput.vue";
import {
  authTypes,
  params,
  searchOrderOptions,
  searchSortOptions,
} from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions, toggleTheme } from "../helpers.js";
import {
  getImportedNoteTitle,
  isSupportedNoteImportFile,
  noteImportAccept,
  noteImportMaxBytes,
} from "../noteImport.js";
import { groupQueryValue, withGroupQuery } from "../routeHelpers.js";
import { clearStoredToken } from "../tokenStorage.js";

const globalStore = useGlobalStore();
const importInput = ref();
const importProgress = ref({
  completedCount: 0,
  currentFileName: "",
  totalCount: 0,
});
const importSummary = ref(createEmptyImportSummary());
const isImporting = ref(false);
const isImportModalVisible = ref(false);
const menu = ref();
const route = useRoute();
const router = useRouter();
const toast = useToast();

defineProps({
  hideLogo: Boolean,
});

const emit = defineEmits(["toggleSearchModal"]);

const currentAuthType = computed(() => globalStore.config?.authType);
const activeGroup = computed(() => {
  return (
    globalStore.currentGroup ||
    globalStore.config?.defaultGroupId ||
    (globalStore.principal?.isAdmin ? "legacy" : undefined)
  );
});
const isAdmin = computed(() => globalStore.principal?.isAdmin === true);
const canAccessAdminUi = computed(
  () => isAdmin.value && currentAuthType.value !== authTypes.readOnly,
);
const isHomeRoute = computed(() => String(route.path || "") === "/" || route.name === "home");
const isLoginRoute = computed(
  () => String(route.path || "").startsWith("/login") || route.name === "login",
);
const showMetrics = computed(() =>
  isHomeRoute.value,
);
const showSearchButton = computed(() => !showMetrics.value && !isLoginRoute.value);
const currentSearchTerm = computed(() => {
  const term = route.query[params.searchTerm];
  return term && term !== "*" ? term : "";
});
const metricBadges = computed(() => [
  {
    label: "Notes",
    value: globalStore.topBarCounts.notes ?? 0,
  },
  {
    label: "Favorites",
    value: globalStore.topBarCounts.favorites ?? 0,
  },
  {
    label: "Tags",
    value: globalStore.topBarCounts.customTags ?? 0,
  },
]);
const allNotesQuery = computed(() => {
  return withGroupQuery(
    {
      [params.searchTerm]: "*",
      [params.sort]: searchSortOptions.lastModified,
      [params.order]: searchOrderOptions.desc,
    },
    activeGroup.value,
    { allowAll: true },
  );
});
const favoritesQuery = computed(() => {
  const query = {
    ...allNotesQuery.value,
    [params.favoriteOnly]: "true",
  };
  return query;
});
const tagsRoute = computed(() => ({
  name: "tags",
  query: withGroupQuery({}, activeGroup.value, { allowAll: true }),
}));
const importProgressDescription = computed(() => {
  if (!importProgress.value.currentFileName) {
    return "Preparing the selected files.";
  }

  return `Current file: ${importProgress.value.currentFileName}`;
});
const importProgressPercent = computed(() => {
  if (!importProgress.value.totalCount) {
    return 0;
  }

  return Math.round(
    (importProgress.value.completedCount / importProgress.value.totalCount) * 100,
  );
});
const importSummaryDescription = computed(() => {
  const failedCount = importSummary.value.failedItems.length;
  const parts = [
    `${importSummary.value.importedCount} imported`,
    `${importSummary.value.renamedItems.length} renamed`,
    `${failedCount} skipped or failed`,
  ];
  return parts.join(" | ");
});
const importSummaryTitle = computed(() =>
  importSummary.value.importedCount > 0 ? "Import complete" : "Nothing imported",
);
const menuItems = computed(() => [
  {
    label: "All Notes",
    icon: mdilNoteMultiple,
    command: () =>
      router.push({
        name: "home",
        query: allNotesQuery.value,
      }),
  },
  {
    label: "Favorites",
    icon: mdiStarOutline,
    command: () =>
      router.push({
        name: "home",
        query: favoritesQuery.value,
      }),
  },
  {
    label: "Download All",
    icon: mdiDownload,
    command: downloadAllHandler,
  },
  {
    label: "Import",
    icon: mdiUpload,
    visible: showNewButton.value,
    command: openImportDialog,
  },
  {
    label: "Tags",
    icon: mdiTagOutline,
    visible: showNewButton.value,
    command: () => router.push(tagsRoute.value),
  },
  {
    label: "Groups & Users",
    icon: mdilPlusCircle,
    visible: canAccessAdminUi.value,
    command: () => router.push({ name: "admin-groups-users" }),
  },
  {
    label: "Toggle Theme",
    icon: mdilMonitor,
    command: toggleTheme,
  },
  {
    separator: true,
    visible: showLogOutButton(),
  },
  {
    label: "Log Out",
    icon: mdilLogout,
    command: logOut,
    visible: showLogOutButton(),
  },
]);

const showNewButton = computed(() => {
  return Boolean(currentAuthType.value) && currentAuthType.value !== authTypes.readOnly;
});
const newNoteRoute = computed(() => ({
  name: "new",
  query: withGroupQuery({}, activeGroup.value),
}));

function downloadAllHandler() {
  const group = isAdmin.value ? "all" : groupQueryValue(activeGroup.value);
  window.location.assign(getAllNotesExportUrl(group));
}

function openImportDialog() {
  if (isImporting.value) {
    return;
  }

  if (resolveImportTargetGroup() === null) {
    toast.add(
      getToastOptions(
        "Select a specific group or My notes before importing.",
        "Import Unavailable",
        "error",
      ),
    );
    return;
  }

  importInput.value?.click();
}

function clearImportInput() {
  if (importInput.value) {
    importInput.value.value = "";
  }
}

function closeImportModal() {
  if (isImporting.value) {
    return;
  }

  isImportModalVisible.value = false;
}

async function bulkImportChangeHandler(event) {
  const files = Array.from(event.target?.files || []);
  clearImportInput();
  if (!files.length) {
    return;
  }

  const targetGroup = resolveImportTargetGroup();
  if (targetGroup === null) {
    toast.add(
      getToastOptions(
        "Select a specific group or My notes before importing.",
        "Import Unavailable",
        "error",
      ),
    );
    return;
  }

  importSummary.value = createEmptyImportSummary();
  importSummary.value.totalSelected = files.length;
  isImportModalVisible.value = true;

  const importableFiles = [];
  for (const file of files) {
    if (!isSupportedNoteImportFile(file)) {
      importSummary.value.failedItems.push({
        fileName: file.name,
        reason: "Unsupported file type. Use .md, .markdown, or .txt.",
      });
      continue;
    }

    if (file.size > noteImportMaxBytes) {
      importSummary.value.failedItems.push({
        fileName: file.name,
        reason: "File is larger than the 2 MB import limit.",
      });
      continue;
    }

    importableFiles.push(file);
  }

  if (!importableFiles.length) {
    toast.add(
      getToastOptions(
        "No supported files were available to import.",
        "Import Finished",
        "error",
      ),
    );
    return;
  }

  isImporting.value = true;
  importProgress.value = {
    completedCount: 0,
    currentFileName: importableFiles[0].name,
    totalCount: importableFiles.length,
  };

  const usedTitles = new Set();
  for (const file of importableFiles) {
    importProgress.value.currentFileName = file.name;

    try {
      const importResult = await importSingleFile(file, targetGroup, usedTitles);
      importSummary.value.importedCount += 1;
      if (importResult.wasRenamed) {
        importSummary.value.renamedItems.push({
          fileName: file.name,
          title: importResult.title,
        });
      }
    } catch (error) {
      console.error(error);
      importSummary.value.failedItems.push({
        fileName: file.name,
        reason: getImportFailureReason(error),
      });
    } finally {
      importProgress.value.completedCount += 1;
    }
  }

  isImporting.value = false;
  importProgress.value.currentFileName = "";
  toast.add(getImportSummaryToast());
  if (importSummary.value.importedCount > 0) {
    window.dispatchEvent(new CustomEvent("copycat:notes-changed"));
  }
}

async function importSingleFile(file, group, usedTitles) {
  const content = await file.text();
  const baseTitle = getImportedNoteTitle(file.name);
  let attempt = 0;

  while (attempt < 100) {
    const candidateTitle =
      attempt === 0 ? baseTitle : `${baseTitle} (${attempt})`;
    if (usedTitles.has(candidateTitle)) {
      attempt += 1;
      continue;
    }

    try {
      const data = await createNote(candidateTitle, content, [], group);
      usedTitles.add(data.title);
      return {
        title: data.title,
        wasRenamed: data.title !== baseTitle,
      };
    } catch (error) {
      if (error.response?.status === 409) {
        attempt += 1;
        continue;
      }
      throw error;
    }
  }

  throw new Error("Unable to find a unique title for this file.");
}

function createEmptyImportSummary() {
  return {
    failedItems: [],
    importedCount: 0,
    renamedItems: [],
    totalSelected: 0,
  };
}

function getImportFailureReason(error) {
  if (error.response?.status === 413) {
    return "File exceeds the server note size limit.";
  }

  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }

  return error.message || "Unable to import the selected file.";
}

function getImportSummaryToast() {
  const importedCount = importSummary.value.importedCount;
  const failedCount = importSummary.value.failedItems.length;
  const renamedCount = importSummary.value.renamedItems.length;

  if (importedCount === 0) {
    return getToastOptions(
      "No notes were imported.",
      "Import Finished",
      "error",
    );
  }

  const summaryParts = [`Imported ${importedCount} notes.`];
  if (renamedCount > 0) {
    summaryParts.push(`${renamedCount} renamed.`);
  }
  if (failedCount > 0) {
    summaryParts.push(`${failedCount} skipped or failed.`);
  }

  return getToastOptions(
    summaryParts.join(" "),
    "Import Finished",
    failedCount > 0 ? "warn" : "success",
  );
}

function resolveImportTargetGroup() {
  if (isAdmin.value && activeGroup.value === "all") {
    return null;
  }

  return activeGroup.value || undefined;
}

function logOut() {
  logout()
    .catch(() => {})
    .finally(() => {
      clearStoredToken();
      localStorage.clear();
      globalStore.principal = null;
      globalStore.config = {
        ...(globalStore.config || {}),
        role: "guest",
        availableGroups: [],
        defaultGroupId: null,
        showLegacyLibrary: false,
        httpOnlyAuthCookie: false,
      };
      globalStore.currentGroup = null;
      globalStore.topBarCounts = {
        notes: 0,
        favorites: 0,
        customTags: 0,
      };
      router.push({ name: "login" });
    });
}

function toggleMenu(event) {
  menu.value.toggle(event);
}

function showLogOutButton() {
  return Boolean(currentAuthType.value) && ![authTypes.none, authTypes.readOnly].includes(currentAuthType.value);
}
</script>
