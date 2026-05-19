<template>
  <div class="flex flex-1 items-center justify-center py-12">
    <div class="app-surface w-full max-w-[560px] rounded-[32px] px-6 py-8 sm:px-8">
      <Logo class="mb-8" />

      <p class="app-kicker">Protected workspace</p>
      <h1 class="text-4xl font-semibold text-theme-text sm:text-5xl">
        Sign in
      </h1>
      <p class="app-subtitle max-w-none">
        Continue to your CopyCat workspace with the current auth flow.
      </p>

      <form @submit.prevent="logIn" class="mt-8 flex flex-col gap-3">
        <TextInput
          v-model="username"
          id="username"
          placeholder="Username"
          autocomplete="username"
          required
        />
        <TextInput
          v-model="password"
          id="password"
          placeholder="Password"
          type="password"
          autocomplete="current-password"
          required
        />
        <TextInput
          v-if="globalStore.config?.authType == authTypes.totp"
          v-model="totp"
          id="one-time-code"
          placeholder="2FA Code"
          autocomplete="one-time-code"
          required
        />
        <label
          for="remember-me"
          class="mt-2 inline-flex items-center gap-3 text-sm text-theme-text-muted"
        >
          <input
            type="checkbox"
            id="remember-me"
            v-model="rememberMe"
            class="accent-[rgb(var(--theme-brand))]"
          />
          Remember Me
        </label>
        <CustomButton
          :iconPath="mdilLogin"
          label="Log In"
          type="submit"
          style="cta"
          class="mt-3 w-full justify-center"
        />
      </form>
    </div>
  </div>
</template>

<script setup>
import { mdilLogin } from "@mdi/light-js";
import { useToast } from "primevue/usetoast";
import { ref } from "vue";
import { useRouter } from "vue-router";

import { apiErrorHandler, authCheck, getConfig, getToken } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import Logo from "../components/Logo.vue";
import TextInput from "../components/TextInput.vue";
import { authTypes } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import { withGroupQuery } from "../routeHelpers.js";
import { setManagedCookieMode, storeToken } from "../tokenStorage.js";

const props = defineProps({ redirect: String });

const globalStore = useGlobalStore();
const router = useRouter();
const toast = useToast();

const username = ref("");
const password = ref("");
const totp = ref("");
const rememberMe = ref(false);

function logIn() {
  getToken(username.value, password.value, totp.value)
    .then((accessToken) => {
      setManagedCookieMode(globalStore.config?.httpOnlyAuthCookie === true);
      storeToken(accessToken, rememberMe.value);
      return Promise.all([getConfig(), authCheck()]);
    })
    .then(([config, principal]) => {
      setManagedCookieMode(config.httpOnlyAuthCookie === true);
      globalStore.config = config;
      globalStore.principal = principal;
      globalStore.currentGroup = config.defaultGroupId || null;
      if (props.redirect) {
        router.push(props.redirect);
      } else {
        router.push({
          name: "home",
          query: withGroupQuery({}, config.defaultGroupId),
        });
      }
    })
    .catch((error) => {
      username.value = "";
      password.value = "";
      totp.value = "";

      if (error.response?.status === 401) {
        toast.add(
          getToastOptions(
            "Please check your credentials and try again.",
            "Login Failed",
            "error",
          ),
        );
      } else {
        apiErrorHandler(error, toast);
      }
    });
}

// Redirect to home if authentication is disabled.
if (globalStore.config?.authType === authTypes.none) {
  router.push({ name: "home" });
}
</script>
