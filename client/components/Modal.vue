<template>
  <!-- Mask -->
  <div
    v-if="isVisible"
    class="fixed inset-0 z-50 flex min-h-dvh items-start justify-center bg-slate-950/45 px-3 py-10 sm:py-16"
    @click.self="closeHandler"
  >
    <!-- Modal -->
    <div
      class="app-surface relative w-full max-w-[720px] rounded-[32px]"
      :class="$attrs.class"
    >
      <slot></slot>
    </div>
  </div>
</template>

<script setup>
import Mousetrap from "mousetrap";

defineOptions({
  inheritAttrs: false,
});
const props = defineProps({
  closeHandlerOverride: Function,
});
const isVisible = defineModel({ type: Boolean });

// 'escape' to close
Mousetrap.bind("esc", () => {
  if (isVisible.value) {
    closeHandler();
  }
});

function closeHandler() {
  if (props.closeHandlerOverride) {
    props.closeHandlerOverride();
  } else {
    isVisible.value = false;
  }
}
</script>
