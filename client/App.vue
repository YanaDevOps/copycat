<template>
  <LoadingIndicator
    ref="loadingIndicator"
    class="min-h-screen print:max-w-full"
  >
    <PrimeToast />
    <SearchModal v-model="isSearchModalVisible" />
    <div class="app-frame">
      <NavBar
        v-if="showNavBar"
        ref="navBar"
        :class="{ 'print:hidden': route.name == 'note' }"
        :hide-logo="!showNavBarLogo"
        @toggleSearchModal="toggleSearchModal"
      />
      <main class="flex flex-1 flex-col">
        <RouterView />
      </main>
    </div>
  </LoadingIndicator>
</template>

<script setup>
import Mousetrap from "mousetrap";
import "mousetrap/plugins/global-bind/mousetrap-global-bind";
import { useToast } from "primevue/usetoast";
import { computed, ref } from "vue";
import { RouterView, useRoute } from "vue-router";

import { apiErrorHandler, authCheck, getConfig } from "./api.js";
import PrimeToast from "./components/PrimeToast.vue";
import { useGlobalStore } from "./globalStore.js";
import { loadTheme } from "./helpers.js";
import NavBar from "./partials/NavBar.vue";
import SearchModal from "./partials/SearchModal.vue";
import LoadingIndicator from "./components/LoadingIndicator.vue";
import { withGroupQuery } from "./routeHelpers.js";
import router from "./router.js";
import { setManagedCookieMode } from "./tokenStorage.js";

const globalStore = useGlobalStore();
const isSearchModalVisible = ref(false);
const loadingIndicator = ref();
const navBar = ref();
const route = useRoute();
const toast = useToast();

// '/' to search
Mousetrap.bind("/", () => {
  if (route.name !== "login") {
    toggleSearchModal();
    return false;
  }
});

// 'CTRL + ALT/OPT + N' to create new note
Mousetrap.bindGlobal("ctrl+alt+n", () => {
  if (route.name !== "login") {
    router.push({
      name: "new",
      query: withGroupQuery({}, globalStore.currentGroup),
    });
    return false;
  }
});

// 'CTRL + ALT/OPT + H' to go to home
Mousetrap.bindGlobal("ctrl+alt+h", () => {
  if (route.name !== "login") {
    const query = withGroupQuery({}, globalStore.currentGroup, {
      allowAll: true,
    });
    router.push({ name: "home", query });
    return false;
  }
});

const isInitialLoginRoute =
  route.name === "login" || String(route.path || "").endsWith("/login");
const initialLoad = isInitialLoginRoute
  ? getConfig()
  : Promise.all([getConfig(), authCheck()]);

initialLoad
  .then((data) => {
    if (Array.isArray(data)) {
      const [config, principal] = data;
      globalStore.config = config;
      setManagedCookieMode(config.httpOnlyAuthCookie === true);
      globalStore.principal = principal;
      if (!globalStore.currentGroup) {
        globalStore.currentGroup = config.defaultGroupId || null;
      }
    } else {
      globalStore.config = data;
      setManagedCookieMode(data.httpOnlyAuthCookie === true);
    }
    loadingIndicator.value.setLoaded();
  })
  .catch((error) => {
    apiErrorHandler(error, toast);
    if (error.response?.status === 401) {
      loadingIndicator.value.setLoaded();
    } else {
      loadingIndicator.value.setFailed();
    }
  });

const isHomeRoute = computed(
  () => String(route.path || "") === "/" || route.name === "home",
);
const isLoginRoute = computed(
  () => String(route.path || "").startsWith("/login") || route.name === "login",
);

const showNavBar = computed(() => {
  return !isLoginRoute.value;
});

const showNavBarLogo = computed(() => {
  return !isHomeRoute.value;
});

function toggleSearchModal() {
  isSearchModalVisible.value = !isSearchModalVisible.value;
}

loadTheme();
</script>
