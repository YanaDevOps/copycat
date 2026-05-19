<template>
  <div class="relative w-full">
    <div
      class="app-surface-muted flex w-full items-center gap-3 rounded-[28px]"
      :class="{ 'px-4 py-3': !large, 'px-5 py-4 sm:px-6 sm:py-5': large }"
    >
      <IconLabel
        :iconPath="mdilMagnify"
        class="shrink-0 text-theme-text-muted"
      />
      <input
        ref="input"
        v-model="searchTerm"
        type="text"
        :autofocus="autoFocus"
        class="w-full bg-transparent text-sm text-theme-text placeholder:text-theme-text-very-muted focus:outline-none sm:text-base"
        :placeholder="placeholder"
        @keydown="keydownHandler"
        @keyup="stateChangeHandler"
        @click="stateChangeHandler"
        @blur="hideTagMenuWithDelay"
        @keydown.down.prevent
        @keydown.up.prevent
      />
    </div>

    <div
      v-if="tagMenuVisible"
      class="app-surface absolute z-10 mt-3 max-h-72 w-full overflow-auto rounded-[24px] p-2"
    >
      <button
        v-for="(tag, index) in tagMatches"
        :key="tag.id"
        ref="tagMenuItems"
        type="button"
        class="flex w-full items-center justify-between rounded-[18px] px-3 py-3 text-left hover:bg-theme-background/45"
        :class="{ 'bg-theme-brand/10': index === tagMenuIndex }"
        @click="tagChosen(tag)"
        @mousedown.prevent
      >
        <span class="font-medium text-theme-text">#{{ tag.id }}</span>
        <span class="text-xs text-theme-text-muted">{{ tag.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { mdilMagnify } from "@mdi/light-js";
import { useToast } from "primevue/usetoast";
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { apiErrorHandler, getTags } from "../api.js";
import IconLabel from "../components/IconLabel.vue";
import * as constants from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { withGroupQuery } from "../routeHelpers.js";

const props = defineProps({
  initialSearchTerm: { type: String, default: "" },
  large: Boolean,
  placeholder: { type: String, default: "Search..." },
  autoFocus: Boolean,
});
const emit = defineEmits(["search"]);

const input = ref();
const globalStore = useGlobalStore();
const route = useRoute();
const router = useRouter();
const searchTerm = ref(props.initialSearchTerm);
const toast = useToast();
let tags = null;
const tagMatches = ref([]);
const tagMenuItems = ref([]);
const tagMenuIndex = ref(0);
const tagMenuVisible = ref(false);

function activeGroup() {
  return (
    route.query[constants.params.group] ||
    globalStore.currentGroup ||
    globalStore.config?.defaultGroupId ||
    (globalStore.principal?.isAdmin ? "legacy" : undefined) ||
    undefined
  );
}

function keydownHandler(event) {
  if (tagMenuVisible.value) {
    if (event.key === "ArrowDown") {
      tagMenuIndex.value = Math.min(
        tagMenuIndex.value + 1,
        tagMatches.value.length - 1,
      );
      tagMenuItems.value[tagMenuIndex.value]?.scrollIntoView({
        block: "nearest",
      });
    } else if (event.key === "ArrowUp") {
      tagMenuIndex.value = Math.max(tagMenuIndex.value - 1, 0);
      tagMenuItems.value[tagMenuIndex.value]?.scrollIntoView({
        block: "nearest",
      });
    } else if (event.key === "Enter") {
      tagChosen(tagMatches.value[tagMenuIndex.value]);
    } else if (event.key === "Escape") {
      tagMenuVisible.value = false;
      event.stopPropagation();
    }
  } else if (event.key === "Enter") {
    search();
  }
}

function tagChosen(tag) {
  if (!tag) {
    return;
  }
  replaceWordOnCursor(`#${tag.id}`);
  tagMenuVisible.value = false;
}

function search() {
  const normalizedSearchTerm = searchTerm.value.trim();
  searchTerm.value = normalizedSearchTerm;

  router.push({
    name: "home",
    query: withGroupQuery(
      normalizedSearchTerm
        ? { [constants.params.searchTerm]: normalizedSearchTerm }
        : {},
      activeGroup(),
      { allowAll: true },
    ),
  });
  emit("search");
}

function stateChangeHandler() {
  const wordOnCursor = getWordOnCursor();
  if (wordOnCursor.charAt(0) !== "#") {
    tagMenuVisible.value = false;
    tagMatches.value = [];
  } else {
    filterTagMatches(wordOnCursor.toLowerCase().replace("#", ""));
  }
}

async function filterTagMatches(inputValue) {
  if (tags === null) {
    try {
      tags = await getTags(activeGroup());
    } catch (error) {
      tags = [];
      apiErrorHandler(error, toast);
    }
  }

  const currentTagMatchCount = tagMatches.value.length;
  tagMatches.value = tags.filter(
    (tag) =>
      tag.id.toLowerCase().startsWith(inputValue) &&
      `#${tag.id.toLowerCase()}` !== `#${inputValue}`,
  );
  if (
    currentTagMatchCount !== tagMatches.value.length &&
    tagMatches.value.length > 0
  ) {
    tagMenuIndex.value = 0;
    tagMenuVisible.value = true;
  } else if (tagMatches.value.length === 0) {
    tagMenuVisible.value = false;
  }
}

function getWordOnCursorPosition() {
  const cursorPosition = input.value.selectionStart;
  const wordStart = Math.max(
    searchTerm.value.lastIndexOf(" ", cursorPosition - 1) + 1,
    0,
  );
  let wordEnd = searchTerm.value.indexOf(" ", cursorPosition);
  if (wordEnd === -1) {
    wordEnd = searchTerm.value.length;
  }
  return { start: wordStart, end: wordEnd };
}

function getWordOnCursor() {
  const { start, end } = getWordOnCursorPosition();
  return searchTerm.value.substring(start, end);
}

function replaceWordOnCursor(replacement) {
  const { start, end } = getWordOnCursorPosition();
  searchTerm.value =
    searchTerm.value.substring(0, start) +
    replacement +
    searchTerm.value.substring(end);
}

function hideTagMenuWithDelay() {
  setTimeout(() => {
    tagMenuVisible.value = false;
  }, 100);
}

watch(
  () => props.initialSearchTerm,
  () => {
    searchTerm.value = props.initialSearchTerm;
  },
);

watch(
  () => route.query[constants.params.group],
  () => {
    tags = null;
    tagMatches.value = [];
    tagMenuVisible.value = false;
  },
);

watch(
  () => globalStore.currentGroup,
  () => {
    tags = null;
    tagMatches.value = [];
    tagMenuVisible.value = false;
  },
);

onMounted(() => {
  if (props.autoFocus) {
    input.value?.focus();
  }
});
</script>
