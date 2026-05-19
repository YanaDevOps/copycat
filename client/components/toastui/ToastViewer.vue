<template>
  <div ref="viewerElement"></div>
</template>

<script setup>
import Viewer from "@toast-ui/editor/dist/toastui-editor-viewer";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import baseOptions from "./baseOptions.js";
import extendedAutolinks from "./extendedAutolinks.js";
import { groupQueryValue } from "../../routeHelpers.js";

const props = defineProps({
  initialValue: String,
  group: {
    type: String,
    default: null,
  },
});

const viewerElement = ref();
let viewer = null;

function withAttachmentGroupQuery(url) {
  const group = groupQueryValue(props.group);
  if (!group || /(^|[?&])group=/.test(url)) {
    return url;
  }

  const [baseWithQuery, hash = ""] = url.split("#", 2);
  const separator = baseWithQuery.includes("?") ? "&" : "?";
  return `${baseWithQuery}${separator}group=${encodeURIComponent(group)}${
    hash ? `#${hash}` : ""
  }`;
}

function normalizeAttachmentUrls(content) {
  if (!content || !groupQueryValue(props.group)) {
    return content || "";
  }

  let normalized = content.replace(
    /(\]\()((?:\/)?attachments\/[^)\s]+)(\))/gi,
    (_, prefix, url, suffix) =>
      `${prefix}${withAttachmentGroupQuery(url)}${suffix}`,
  );
  normalized = normalized.replace(
    /((?:src|href)=["'])((?:\/)?attachments\/[^"']+)(["'])/gi,
    (_, prefix, url, suffix) =>
      `${prefix}${withAttachmentGroupQuery(url)}${suffix}`,
  );
  return normalized;
}

function normalizeSvgDimensions(content) {
  return (content || "").replace(/<svg\b([^>]*)>/gi, (_, attributes) => {
    const sanitizedAttributes = attributes
      .replace(/\s(width|height)=["']auto["']/gi, "")
      .trim();
    return `<svg${sanitizedAttributes ? ` ${sanitizedAttributes}` : ""}>`;
  });
}

function normalizedValue() {
  return normalizeSvgDimensions(normalizeAttachmentUrls(props.initialValue));
}

function renderViewer() {
  if (!viewerElement.value) {
    return;
  }

  viewer?.destroy?.();
  viewerElement.value.innerHTML = "";
  viewer = new Viewer({
    ...baseOptions,
    extendedAutolinks,
    el: viewerElement.value,
    initialValue: normalizedValue(),
  });
}

onMounted(renderViewer);

watch(
  () => [props.initialValue, props.group],
  () => {
    renderViewer();
  },
);

onBeforeUnmount(() => {
  viewer?.destroy?.();
});
</script>

<style>
@import "@toast-ui/editor/dist/toastui-editor-viewer.css";
@import "prismjs/themes/prism.css";
@import "@toast-ui/editor-plugin-code-syntax-highlight/dist/toastui-editor-plugin-code-syntax-highlight.css";
@import "./toastui-editor-overrides.scss";
</style>
