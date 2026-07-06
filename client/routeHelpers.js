import { params } from "./constants.js";

export const legacyGroup = "legacy";
export const allGroups = "all";

export function normalizeGroupValue(value) {
  const normalized = String(value || "").trim();
  return normalized || undefined;
}

export function isLegacyGroup(value) {
  return normalizeGroupValue(value)?.toLowerCase() === legacyGroup;
}

export function groupQueryValue(value, { allowAll = false } = {}) {
  const normalized = normalizeGroupValue(value);
  if (!normalized || isLegacyGroup(normalized)) {
    return undefined;
  }
  if (normalized.toLowerCase() === allGroups && !allowAll) {
    return undefined;
  }
  return normalized;
}

export function withGroupQuery(query = {}, group, options = {}) {
  const nextQuery = { ...query };
  const groupValue = groupQueryValue(group, options);
  delete nextQuery[params.group];
  if (groupValue) {
    nextQuery[params.group] = groupValue;
  }
  return nextQuery;
}

export function cleanNoteTitleForRoute(title) {
  return String(title || "").trim();
}

export function noteRouteLocation(title, group, options = {}) {
  return {
    path: `/note/${encodeURIComponent(cleanNoteTitleForRoute(title))}`,
    query: withGroupQuery({}, group, options),
  };
}

export function cleanWikiLinkTitle(title) {
  let normalized = cleanNoteTitleForRoute(title);
  if (normalized.startsWith("[") && normalized.endsWith("]")) {
    const inner = normalized.slice(1, -1).trim();
    if (inner) {
      normalized = inner;
    }
  }
  return normalized;
}

export function canonicalizeLegacyGroupQuery(route) {
  if (!isLegacyGroup(route.query?.[params.group])) {
    return null;
  }
  const query = { ...route.query };
  delete query[params.group];
  const target = route.name
    ? { name: route.name, params: route.params }
    : { path: route.path };
  return {
    ...target,
    query,
    hash: route.hash,
    replace: true,
  };
}

export function canonicalizeNotePathEncoding(route) {
  if (
    route.name !== "note" ||
    !route.params?.title ||
    !/[\[\]]/.test(route.path)
  ) {
    return null;
  }
  return {
    path: `/note/${encodeURIComponent(cleanNoteTitleForRoute(route.params.title))}`,
    query: { ...route.query },
    hash: route.hash,
    replace: true,
  };
}
