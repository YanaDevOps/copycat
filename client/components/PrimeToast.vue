<template>
  <Toast position="bottom-right" :pt="style" />
</template>

<script setup>
import Toast from "primevue/toast";

const style = {
  message: "flex flex-col items-end ml-[20px]",
  container: ({ props }) => ({
    class: [
      "mt-3 max-w-96 rounded-[22px] border px-4 py-3 shadow-[0_20px_60px_rgb(var(--theme-shadow)/0.18)]",
      "bg-theme-panel-strong/95 border-theme-border",
      {
        "border-theme-success/45": props.message.severity == "success",
        "border-theme-danger/45": props.message.severity == "error",
      },
    ],
  }),
  icon: "invisible h-0 w-0",
  summary: "font-semibold text-theme-text",
  detail: "mt-1 text-sm leading-6 text-theme-text-muted",
};
</script>
