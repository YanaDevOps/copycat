<template>
  <div ref="root" class="relative inline-flex max-w-full">
    <div @click.stop="toggle">
      <slot name="trigger"></slot>
    </div>
    <div
      v-if="isOpen && !teleport"
      class="absolute z-[90] max-h-[min(28rem,70vh)] max-w-[calc(100vw-2rem)] min-w-[16rem] overflow-auto rounded-[24px] border border-theme-border bg-theme-panel-strong/95 p-3 shadow-[0_24px_80px_rgb(var(--theme-shadow)/0.18)]"
      :class="[
        {
          'left-0': align === 'left',
          'right-0': align === 'right',
          'top-full mt-3': side === 'bottom',
          'bottom-full mb-3': side === 'top',
        },
        panelClass,
      ]"
    >
      <slot :close="close"></slot>
    </div>
    <Teleport to="body">
      <div
        v-if="isOpen && teleport"
        ref="panel"
        class="z-[90] max-h-[min(28rem,70vh)] max-w-[calc(100vw-2rem)] min-w-[16rem] overflow-auto rounded-[24px] border border-theme-border bg-theme-panel-strong/95 p-3 shadow-[0_24px_80px_rgb(var(--theme-shadow)/0.18)]"
        :class="panelClass"
        :style="panelStyle"
      >
        <slot :close="close"></slot>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { Teleport, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  align: {
    type: String,
    default: "right",
  },
  side: {
    type: String,
    default: "bottom",
  },
  panelClass: {
    type: [String, Array, Object],
    default: "",
  },
  teleport: Boolean,
});

const PANEL_GAP = 12;
const VIEWPORT_PADDING = 16;
const root = ref();
const panel = ref();
const isOpen = ref(false);
const panelStyle = ref({});
let resizeObserver = null;

function toggle() {
  if (isOpen.value) {
    close();
    return;
  }
  isOpen.value = true;
}

function close() {
  isOpen.value = false;
}

function reposition() {
  updatePanelPosition();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function updatePanelPosition() {
  if (!props.teleport || !isOpen.value || !root.value || !panel.value) {
    return;
  }

  const triggerRect = root.value.getBoundingClientRect();
  const panelWidth = panel.value.offsetWidth;
  const panelHeight = panel.value.offsetHeight;
  const maxLeft = Math.max(
    VIEWPORT_PADDING,
    window.innerWidth - panelWidth - VIEWPORT_PADDING,
  );
  const left = clamp(
    props.align === "left"
      ? triggerRect.left
      : triggerRect.right - panelWidth,
    VIEWPORT_PADDING,
    maxLeft,
  );
  const maxTop = Math.max(
    VIEWPORT_PADDING,
    window.innerHeight - panelHeight - VIEWPORT_PADDING,
  );
  const top = clamp(
    props.side === "top"
      ? triggerRect.top - panelHeight - PANEL_GAP
      : triggerRect.bottom + PANEL_GAP,
    VIEWPORT_PADDING,
    maxTop,
  );

  panelStyle.value = {
    position: "fixed",
    left: `${left}px`,
    top: `${top}px`,
  };
}

function handleDocumentClick(event) {
  if (root.value?.contains(event.target) || panel.value?.contains(event.target)) {
    return;
  }
  close();
}

function handleEscape(event) {
  if (event.key === "Escape") {
    close();
  }
}

function handleViewportChange() {
  updatePanelPosition();
}

function disconnectResizeObserver() {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
}

function observePanelSize() {
  if (
    !props.teleport ||
    !panel.value ||
    typeof ResizeObserver === "undefined"
  ) {
    return;
  }

  disconnectResizeObserver();
  resizeObserver = new ResizeObserver(() => {
    updatePanelPosition();
  });
  resizeObserver.observe(panel.value);
}

onMounted(() => {
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("keydown", handleEscape);
  window.addEventListener("resize", handleViewportChange);
  document.addEventListener("scroll", handleViewportChange, true);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", handleDocumentClick);
  document.removeEventListener("keydown", handleEscape);
  window.removeEventListener("resize", handleViewportChange);
  document.removeEventListener("scroll", handleViewportChange, true);
  disconnectResizeObserver();
});

watch(isOpen, async (open) => {
  if (open && props.teleport) {
    await nextTick();
    observePanelSize();
    updatePanelPosition();
  } else {
    disconnectResizeObserver();
  }
});

watch(panel, async (element) => {
  if (!props.teleport) {
    return;
  }

  if (element) {
    await nextTick();
    observePanelSize();
    updatePanelPosition();
  } else {
    disconnectResizeObserver();
  }
});

defineExpose({ close, reposition });
</script>
