import * as constants from "./constants.js";

import { createRouter, createWebHistory } from "vue-router";

import { authCheck } from "./api.js";
import {
  canonicalizeLegacyGroupQuery,
  canonicalizeNotePathEncoding,
} from "./routeHelpers.js";

function getQueryStringValue(value) {
  return Array.isArray(value) ? value[0] : value;
}

function parseTagIds(queryValue) {
  const rawValue = getQueryStringValue(queryValue);
  if (!rawValue) {
    return [];
  }
  return rawValue
    .split(",")
    .map((tagId) => tagId.trim())
    .filter(Boolean);
}

function parseGroup(queryValue) {
  const value = getQueryStringValue(queryValue);
  return value || undefined;
}

const router = createRouter({
  history: createWebHistory(""),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("./views/Home.vue"),
      props: (route) => ({
        searchTerm:
          getQueryStringValue(route.query[constants.params.searchTerm]) ||
          undefined,
        sort: getQueryStringValue(route.query[constants.params.sort]),
        order:
          getQueryStringValue(route.query[constants.params.order]) || undefined,
        tagIds: parseTagIds(route.query[constants.params.tagIds]),
        favoriteOnly:
          getQueryStringValue(route.query[constants.params.favoriteOnly]) ===
          "true",
        group: parseGroup(route.query[constants.params.group]),
      }),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("./views/LogIn.vue"),
      props: (route) => ({ redirect: route.query[constants.params.redirect] }),
    },
    {
      path: "/note/:title",
      name: "note",
      component: () => import("./views/Note.vue"),
      props: (route) => ({
        title: route.params.title,
        group: parseGroup(route.query[constants.params.group]),
      }),
    },
    {
      path: "/new",
      name: "new",
      component: () => import("./views/Note.vue"),
      props: (route) => ({
        group: parseGroup(route.query[constants.params.group]),
      }),
    },
    {
      path: "/tags",
      name: "tags",
      component: () => import("./views/Tags.vue"),
      props: (route) => ({
        group: parseGroup(route.query[constants.params.group]),
      }),
    },
    {
      path: "/search",
      redirect: (to) => ({
        name: "home",
        query: to.query,
      }),
    },
    {
      path: "/admin/groups-users",
      name: "admin-groups-users",
      component: () => import("./views/AdminGroupsUsers.vue"),
    },
  ],
});

// Check the user is authenticated on first navigation (unless going to login)
let authChecked = false;
router.beforeEach(async (to) => {
  const canonicalRoute = canonicalizeLegacyGroupQuery(to);
  if (canonicalRoute) {
    return canonicalRoute;
  }
  const canonicalNoteRoute = canonicalizeNotePathEncoding(to);
  if (canonicalNoteRoute) {
    return canonicalNoteRoute;
  }
  if (authChecked || to.name === "login") {
    return;
  }
  try {
    await authCheck();
    return;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      return {
        name: "login",
        query: { [constants.params.redirect]: to.fullPath },
      };
    }
  } finally {
    authChecked = true;
  }
});

router.afterEach((to) => {
  let title = "CopyCat";
  if (to.name === "note") {
    if (to.params.title) {
      title = `${to.params.title} - ${title}`;
    } else {
      title = "New Note - " + title;
    }
  } else if (to.name === "tags") {
    title = `Tags - ${title}`;
  } else if (to.name === "admin-groups-users") {
    title = `Groups & Users - ${title}`;
  }
  document.title = title;
});

export default router;
