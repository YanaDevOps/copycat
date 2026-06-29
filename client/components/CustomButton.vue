<template>
  <button
    :type="type"
    :disabled="disabled"
    class="app-button group relative inline-flex items-center justify-center gap-2 whitespace-nowrap border font-medium shadow-[0_12px_32px_rgb(var(--theme-shadow)/0.08)]"
    :class="buttonClass"
    :aria-label="label"
    :title="label"
  >
    <slot></slot>
    <IconLabel
      :iconPath="iconPath"
      :iconSize="resolvedIconSize"
      :label="iconOnly ? undefined : label"
    />
    <span v-if="iconOnly && label" class="sr-only">{{ label }}</span>
  </button>
</template>

<script setup>
import { computed } from "vue";

import IconLabel from "./IconLabel.vue";

const props = defineProps({
  iconPath: String,
  iconSize: String,
  label: String,
  iconOnly: Boolean,
  disabled: Boolean,
  type: {
    type: String,
    default: "button",
    validator: (value) => {
      return ["button", "submit", "reset"].includes(value);
    },
  },
  size: {
    type: String,
    default: "md",
    validator: (value) => {
      return ["sm", "md"].includes(value);
    },
  },
  style: {
    type: String,
    default: "subtle",
    validator: (value) => {
      return ["subtle", "cta", "danger", "success"].includes(value);
    },
  },
});

const resolvedIconSize = computed(() => {
  if (props.iconSize) {
    return props.iconSize;
  }

  return props.size === "sm" ? "1.05em" : "1.15em";
});

const buttonClass = computed(() => ({
  "h-9 rounded-full px-3 text-xs": props.size === "sm" && !props.iconOnly,
  "h-10 rounded-full px-4 py-2.5 text-sm":
    props.size === "md" && !props.iconOnly,
  "h-9 w-9 rounded-full p-0": props.size === "sm" && props.iconOnly,
  "h-10 w-10 rounded-full p-0": props.size === "md" && props.iconOnly,
  "app-button-enabled": !props.disabled,
  "border-theme-border bg-theme-panel/75 text-theme-text hover:border-theme-brand/30 hover:bg-theme-panel-strong/90":
    props.style === "subtle",
  "border-theme-brand/35 bg-theme-brand/10 text-theme-text hover:border-theme-brand/55 hover:bg-theme-brand/15":
    props.style === "cta",
  "border-theme-danger/35 bg-theme-danger/10 text-theme-danger hover:bg-theme-danger/15":
    props.style === "danger",
  "border-theme-success/35 bg-theme-success/10 text-theme-success hover:bg-theme-success/15":
    props.style === "success",
  "pointer-events-none opacity-45 shadow-none":
    props.disabled,
}));
</script>
