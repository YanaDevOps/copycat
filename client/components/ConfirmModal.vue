<template>
  <Modal
    v-model="isVisible"
    :closeHandlerOverride="emitClose"
    class="px-6 py-6 sm:px-8"
  >
    <!-- Title -->
    <div v-if="title" class="mb-3 text-2xl font-semibold text-theme-text">
      {{ title }}
    </div>
    <!-- Message -->
    <div class="mb-8 text-sm leading-7 text-theme-text-muted">{{ message }}</div>
    <!-- Buttons -->
    <div class="flex flex-wrap justify-end gap-2">
      <CustomButton
        :label="cancelButtonText"
        :style="cancelButtonStyle"
        @click="emitClose('cancel')"
      />
      <CustomButton
        v-if="rejectButtonText"
        :label="rejectButtonText"
        :style="rejectButtonStyle"
        @click="emitClose('reject')"
      />
      <CustomButton
        v-focus
        :label="confirmButtonText"
        :style="confirmButtonStyle"
        @click="emitClose('confirm')"
      />
    </div>
  </Modal>
</template>

<script setup>
import CustomButton from "./CustomButton.vue";
import Modal from "./Modal.vue";

const props = defineProps({
  title: { type: String, default: "Confirmation" },
  message: String,
  confirmButtonStyle: { type: String, default: "cta" },
  confirmButtonText: { type: String, default: "Confirm" },
  cancelButtonStyle: { type: String, default: "subtle" },
  cancelButtonText: { type: String, default: "Cancel" },
  rejectButtonStyle: { type: String, default: "danger" },
  rejectButtonText: { type: String },
});
const emit = defineEmits(["confirm", "reject", "cancel"]);
const isVisible = defineModel({ type: Boolean });

function emitClose(closeEvent = "cancel") {
  isVisible.value = false;
  emit(closeEvent);
}
</script>
