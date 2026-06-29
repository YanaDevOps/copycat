<template>
  <Menu ref="menu" :pt="style">
    <template #item="{ item, props }">
      <a class="flex items-center justify-between" v-bind="props.action">
        <IconLabel :iconPath="item.icon" :label="item.label" />
        <span
          v-if="item.keyboardShortcut"
          class="ml-4 rounded-full border border-theme-border/70 bg-theme-background/35 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-theme-text-very-muted"
          >{{ item.keyboardShortcut }}</span
        >
      </a>
    </template>
  </Menu>
</template>
<script setup>
import Menu from "primevue/menu";
import { ref } from "vue";

import IconLabel from "./IconLabel.vue";

const menu = ref();

const style = {
  root: "w-[260px] rounded-[24px] border border-theme-border bg-theme-panel-strong/95 p-2 shadow-[0_24px_80px_rgb(var(--theme-shadow)/0.18)]",
  menuitem: ({ context }) => ({
    class: [
      "rounded-[18px] px-3 py-3 text-theme-text-muted",
      "hover:cursor-pointer hover:bg-theme-background/45 hover:text-theme-text",
      {
        "bg-theme-brand/10 text-theme-text": context.focused,
      },
    ],
  }),
  separator: "my-2 border-t border-theme-border/70",
};

function toggle(event) {
  menu.value.toggle(event);
}

defineExpose({ toggle });
</script>
