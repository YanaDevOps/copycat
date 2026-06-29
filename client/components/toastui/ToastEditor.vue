<template>
  <div ref="editorElement" class="toast-editor-root"></div>
</template>

<script setup>
import Editor from "@toast-ui/editor";
import { onBeforeUnmount, onMounted, ref } from "vue";

import { buildBaseOptions } from "./baseOptions.js";

const props = defineProps({
  initialValue: String,
  initialEditType: {
    type: String,
    default: "markdown",
  },
  height: {
    type: String,
    default: "",
  },
  addImageBlobHook: Function,
});

const emit = defineEmits(["change", "keydown"]);

const editorElement = ref();
let toastEditor;
let removePasteListener = null;
let pasteRestoreDeadline = 0;
let mountRequestId = 0;

onMounted(async () => {
  const requestId = ++mountRequestId;
  const editorHeight =
    props.height ||
    (window.matchMedia("(max-width: 767px)").matches ? "420px" : "620px");
  const baseOptions = await buildBaseOptions({ codeSyntaxHighlight: true });
  if (requestId !== mountRequestId || !editorElement.value) {
    return;
  }

  toastEditor = new Editor({
    ...baseOptions,
    el: editorElement.value,
    height: editorHeight,
    initialValue: props.initialValue,
    initialEditType: props.initialEditType,
    events: {
      change: () => {
        emit("change");
      },
      keydown: (_, event) => {
        emit("keydown", event);
      },
    },
    hooks: props.addImageBlobHook
      ? { addImageBlobHook: props.addImageBlobHook }
      : {},
  });

  bindPasteScrollGuard();
});

onBeforeUnmount(() => {
  mountRequestId += 1;
  removePasteListener?.();
  removePasteListener = null;
  toastEditor?.destroy?.();
});

function getMarkdown() {
  return toastEditor.getMarkdown();
}

function setMarkdown(markdown) {
  toastEditor.setMarkdown(markdown ?? "");
}

function isWysiwygMode() {
  return toastEditor.isWysiwygMode();
}

function bindPasteScrollGuard() {
  if (!editorElement.value) {
    return;
  }

  const handlePaste = (event) => {
    const target =
      event.target instanceof HTMLElement ? event.target : editorElement.value;
    const scrollStates = captureScrollStates(target);
    if (scrollStates.length === 0) {
      return;
    }

    // TOAST UI mutates the editor DOM asynchronously during paste, so restore
    // the scroll position after the browser and editor finish their updates.
    schedulePasteScrollRestores(scrollStates);
  };

  editorElement.value.addEventListener("paste", handlePaste, true);
  removePasteListener = () => {
    editorElement.value?.removeEventListener("paste", handlePaste, true);
  };
}

function captureScrollStates(startElement) {
  const scrollStates = [];
  const seen = new Set();

  addElementScrollState(scrollStates, seen, document.scrollingElement);
  addEditorScrollStates(scrollStates, seen);

  let current = startElement;
  while (current instanceof HTMLElement) {
    if (seen.has(current)) {
      current = current.parentElement;
      continue;
    }

    addElementScrollState(scrollStates, seen, current);
    current = current.parentElement;
  }

  scrollStates.push({
    type: "window",
    top: window.scrollY,
    left: window.scrollX,
  });

  return scrollStates;
}

function addEditorScrollStates(scrollStates, seen) {
  const selectors = [
    ".toastui-editor-defaultUI",
    ".toastui-editor-main",
    ".toastui-editor-main-container",
    ".toastui-editor-md-container",
    ".toastui-editor-ww-container",
    ".toastui-editor-md-editor",
    ".toastui-editor-md-preview",
    ".toastui-editor-contents",
    ".ProseMirror",
  ];

  selectors.forEach((selector) => {
    editorElement.value
      ?.querySelectorAll(selector)
      .forEach((element) => addElementScrollState(scrollStates, seen, element));
  });
}

function addElementScrollState(scrollStates, seen, element) {
  if (!(element instanceof HTMLElement) || seen.has(element)) {
    return;
  }

  seen.add(element);
  if (!isScrollable(element)) {
    return;
  }

  scrollStates.push({
    type: "element",
    element,
    top: element.scrollTop,
    left: element.scrollLeft,
  });
}

function schedulePasteScrollRestores(scrollStates) {
  pasteRestoreDeadline = Date.now() + 300;
  restoreScrollStates(scrollStates);
  Promise.resolve().then(() => restoreScrollStates(scrollStates));
  requestAnimationFrame(() => {
    restoreScrollStates(scrollStates);
    requestAnimationFrame(() => restoreScrollStates(scrollStates));
  });
  setTimeout(() => restoreScrollStates(scrollStates), 50);
  setTimeout(() => restoreScrollStates(scrollStates), 150);
}

function restoreScrollStates(scrollStates) {
  if (Date.now() > pasteRestoreDeadline) {
    return;
  }

  for (const state of scrollStates) {
    if (state.type === "window") {
      window.scrollTo(state.left, state.top);
      continue;
    }

    if (!state.element?.isConnected) {
      continue;
    }

    state.element.scrollTop = state.top;
    state.element.scrollLeft = state.left;
  }
}

function isScrollable(element) {
  const style = window.getComputedStyle(element);
  const overflowY = style.overflowY;
  const overflowX = style.overflowX;
  const canScrollY =
    ["auto", "scroll", "overlay"].includes(overflowY) &&
    element.scrollHeight > element.clientHeight;
  const canScrollX =
    ["auto", "scroll", "overlay"].includes(overflowX) &&
    element.scrollWidth > element.clientWidth;

  return canScrollY || canScrollX;
}

defineExpose({ getMarkdown, setMarkdown, isWysiwygMode });
</script>

<style>
@import "@toast-ui/editor/dist/toastui-editor.css";
@import "./toastui-editor-overrides.scss";

.toast-editor-root {
  min-height: 420px;
}

@media (min-width: 768px) {
  .toast-editor-root {
    min-height: 620px;
  }
}
</style>
