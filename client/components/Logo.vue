<template>
  <div class="flex items-center gap-3">
    <img
      :src="copycatLogo"
      alt="CopyCat"
      class="h-10 w-10 rounded-[14px] object-cover shadow-[0_14px_36px_rgb(var(--theme-shadow)/0.16)]"
    />
    <div class="min-w-0" :class="{ 'hidden sm:block': props.responsive }">
      <span
        class="block text-lg font-semibold text-theme-text sm:text-xl"
      >
        CopyCat
      </span>
    </div>
  </div>
</template>

<script setup>
import copycatLogo from "../assets/copycat-logo.png";

const props = defineProps({
  responsive: {
    type: Boolean,
    default: false,
  },
});
</script>
