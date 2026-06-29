<template>
  <article
    class="flex h-full cursor-pointer flex-col overflow-hidden"
    :class="compact ? 'gap-1' : 'gap-1.5'"
    @click="$emit('open')"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0 flex-1" :class="compact ? 'space-y-1.5' : 'space-y-2'">
        <div
          class="note-card-title line-clamp-2 break-words text-base font-semibold text-theme-text sm:text-lg"
          :class="{ 'note-card-title-fade': titleFade }"
          v-html="sanitizedTitleMarkup"
        ></div>
        <div class="flex flex-wrap items-center gap-1.5">
          <span v-if="showGroup && result.groupName" class="note-card-group-pill">
            {{ result.groupName }}
          </span>
          <div v-if="visibleTags.length" class="note-card-tags">
            <Tag v-for="tag in visibleTags" :key="tag.id" :tag="tag" />
            <span v-if="hiddenTagCount > 0" class="note-card-tag-overflow">
              +{{ hiddenTagCount }}
            </span>
          </div>
        </div>
      </div>

      <CustomButton
        v-if="showActions && canModify"
        :iconPath="result.favorite ? mdiStar : mdiStarOutline"
        :label="result.favorite ? 'Unfavorite' : 'Favorite'"
        iconOnly
        size="sm"
        @click.stop.prevent="$emit('toggleFavorite')"
      />
    </div>

    <div
      v-if="showContentHighlights && result.contentHighlights"
      class="note-card-preview"
      :class="compact ? 'note-card-preview-compact' : 'note-card-preview-full'"
    >
      <span
        class="note-card-preview-content"
        v-html="sanitizedContentHighlights"
      ></span>
    </div>

    <div
      class="mt-auto flex items-end justify-between gap-4"
      :class="compact ? 'pt-1.5' : 'pt-2'"
    >
      <div class="min-w-0 text-sm text-theme-text-muted">
        <div>Updated {{ updatedLabel }}</div>
        <div class="mt-1 text-xs text-theme-text-very-muted">
          Created {{ createdLabel }}
        </div>
      </div>

      <div v-if="showActions" class="flex shrink-0 items-center gap-2">
        <CustomButton
          v-if="canModify"
          :iconPath="mdiContentCopy"
          label="Duplicate"
          iconOnly
          size="sm"
          @click.stop.prevent="$emit('duplicate')"
        />
        <Popover
          v-if="showActions && canModify && allowQuickTagging"
          align="right"
          side="top"
          panelClass="note-card-tag-popover"
          teleport
        >
          <template #trigger>
            <CustomButton
              :iconPath="mdiTagOutline"
              label="Tags"
              iconOnly
              size="sm"
            />
          </template>

          <template #default>
            <div class="space-y-3" @click.stop>
              <div class="flex items-center justify-between gap-3">
                <p
                  class="text-[11px] font-semibold uppercase tracking-[0.24em] text-theme-text-very-muted"
                >
                  Tags
                </p>
                <span class="meta-pill">
                  {{ selectedTagIds.length }}/{{ maxNoteTags }}
                </span>
              </div>

              <div v-if="availableTags.length" class="note-card-tag-picker-grid">
                <div
                  v-for="tag in availableTags"
                  :key="tag.id"
                  class="note-card-tag-picker-item"
                >
                  <Tag
                    :tag="tag"
                    clickable
                    :selected="selectedTagIds.includes(tag.id)"
                    @click="$emit('toggleTag', tag.id)"
                  />
                </div>
              </div>

              <p v-else class="text-sm leading-6 text-theme-text-muted">
                No reusable tags yet.
              </p>
            </div>
          </template>
        </Popover>
        <CustomButton
          :iconPath="mdiDownload"
          label="Export"
          iconOnly
          size="sm"
          @click.stop.prevent="$emit('export')"
        />
        <CustomButton
          v-if="canModify"
          :iconPath="mdilDelete"
          label="Delete"
          iconOnly
          size="sm"
          style="danger"
          @click.stop.prevent="$emit('delete')"
        />
      </div>
    </div>
  </article>
</template>

<script setup>
import {
  mdiContentCopy,
  mdiDownload,
  mdiStar,
  mdiStarOutline,
  mdiTagOutline,
} from "@mdi/js";
import { mdilDelete } from "@mdi/light-js";
import { computed } from "vue";

import CustomButton from "./CustomButton.vue";
import Popover from "./Popover.vue";
import Tag from "./Tag.vue";
import { maxNoteTags } from "../constants.js";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  year: "numeric",
});
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const sanitizedMarkupCache = new Map();
const sanitizedMarkupCacheLimit = 800;

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
  showActions: {
    type: Boolean,
    default: true,
  },
  compact: Boolean,
  showGroup: Boolean,
  showContentHighlights: {
    type: Boolean,
    default: true,
  },
  canModify: Boolean,
  availableTags: {
    type: Array,
    default: () => [],
  },
  allowQuickTagging: Boolean,
  maxVisibleTags: {
    type: Number,
    default: 4,
  },
  titleFade: Boolean,
});

defineEmits([
  "open",
  "toggleFavorite",
  "duplicate",
  "export",
  "delete",
  "toggleTag",
]);

const createdLabel = computed(() => formatDate(props.result.createdAt, "date"));
const hiddenTagCount = computed(() =>
  Math.max((props.result.tags?.length || 0) - visibleTags.value.length, 0),
);
const sanitizedContentHighlights = computed(() =>
  sanitizeHighlightMarkup(props.result.contentHighlights || ""),
);
const sanitizedTitleMarkup = computed(() =>
  sanitizeHighlightMarkup(props.result.titleHighlightsOrTitle || props.result.title),
);
const updatedLabel = computed(() =>
  formatDate(props.result.lastModified, "datetime"),
);
const visibleTags = computed(() =>
  (props.result.tags || []).slice(0, props.maxVisibleTags),
);
const selectedTagIds = computed(() => (props.result.tags || []).map((tag) => tag.id));

function formatDate(unixTimestamp, variant = "datetime") {
  if (!unixTimestamp) {
    return "Unknown";
  }

  const formatter = variant === "date" ? dateFormatter : dateTimeFormatter;
  return formatter.format(new Date(unixTimestamp * 1000));
}

function sanitizeHighlightMarkup(markup) {
  if (!markup) {
    return "";
  }
  if (sanitizedMarkupCache.has(markup)) {
    return sanitizedMarkupCache.get(markup);
  }
  if (typeof DOMParser === "undefined") {
    return markup;
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${markup}</div>`, "text/html");
  const container = doc.body.firstElementChild;
  if (!container) {
    return "";
  }

  sanitizeNode(container);
  return cacheSanitizedMarkup(markup, container.innerHTML);
}

function cacheSanitizedMarkup(markup, sanitizedMarkup) {
  if (sanitizedMarkupCache.size >= sanitizedMarkupCacheLimit) {
    const [oldestKey] = sanitizedMarkupCache.keys();
    sanitizedMarkupCache.delete(oldestKey);
  }
  sanitizedMarkupCache.set(markup, sanitizedMarkup);
  return sanitizedMarkup;
}

function sanitizeNode(node) {
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      continue;
    }

    if (child.nodeType !== Node.ELEMENT_NODE) {
      child.remove();
      continue;
    }

    const tagName = child.tagName.toLowerCase();
    const classes = (child.getAttribute("class") || "")
      .split(/\s+/)
      .filter(Boolean);
    const isAllowedTag = ["span", "b"].includes(tagName);
    const hasAllowedClasses =
      classes.length > 0 &&
      classes.every((className) => className === "match" || /^term\d+$/.test(className));

    if (!isAllowedTag || !hasAllowedClasses) {
      child.replaceWith(...Array.from(child.childNodes));
      continue;
    }

    for (const attribute of Array.from(child.attributes)) {
      if (attribute.name !== "class") {
        child.removeAttribute(attribute.name);
      }
    }

    sanitizeNode(child);
  }
}
</script>
