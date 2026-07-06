import assert from "node:assert/strict";
import { test } from "node:test";

import {
  allGroups,
  canonicalizeLegacyGroupQuery,
  canonicalizeNotePathEncoding,
  cleanNoteTitleForRoute,
  cleanWikiLinkTitle,
  groupQueryValue,
  legacyGroup,
  noteRouteLocation,
  withGroupQuery,
} from "../../client/routeHelpers.js";

test("legacy group is not exposed in query strings", () => {
  assert.equal(groupQueryValue(legacyGroup), undefined);
  assert.deepEqual(withGroupQuery({ term: "*" }, legacyGroup), { term: "*" });
});

test("real groups are exposed in query strings", () => {
  assert.equal(groupQueryValue("team"), "team");
  assert.deepEqual(withGroupQuery({ term: "*" }, "team"), {
    term: "*",
    group: "team",
  });
});

test("all group is only exposed when explicitly allowed", () => {
  assert.equal(groupQueryValue(allGroups), undefined);
  assert.equal(groupQueryValue(allGroups, { allowAll: true }), allGroups);
});

test("legacy group query canonicalizes away", () => {
  assert.deepEqual(
    canonicalizeLegacyGroupQuery({
      name: "note",
      path: "/note/Dedi",
      params: { title: "Dedi" },
      query: { group: legacyGroup, term: "*" },
      hash: "#part",
    }),
    {
      name: "note",
      params: { title: "Dedi" },
      query: { term: "*" },
      hash: "#part",
      replace: true,
    },
  );
});

test("note route title only trims normal route titles", () => {
  assert.equal(cleanNoteTitleForRoute("  Dedi Migration 2026  "), "Dedi Migration 2026");
  assert.equal(cleanNoteTitleForRoute("[ Dedi Migration 2026 ]"), "[ Dedi Migration 2026 ]");
});

test("note route location encodes path-only unsafe title characters", () => {
  assert.deepEqual(noteRouteLocation("[ Retn BGP-communities ]"), {
    path: "/note/%5B%20Retn%20BGP-communities%20%5D",
    query: {},
  });
  assert.deepEqual(noteRouteLocation("Dedi Migration 2026", "team"), {
    path: "/note/Dedi%20Migration%202026",
    query: { group: "team" },
  });
});

test("note route location does not double encode raw percent-like titles", () => {
  assert.deepEqual(noteRouteLocation("%5B Retn %5D"), {
    path: "/note/%255B%20Retn%20%255D",
    query: {},
  });
});

test("raw bracket note paths canonicalize to encoded paths", () => {
  assert.deepEqual(
    canonicalizeNotePathEncoding({
      name: "note",
      path: "/note/[%20Retn%20BGP-communities%20]",
      params: { title: "[ Retn BGP-communities ]" },
      query: { group: "team" },
      hash: "#part",
    }),
    {
      path: "/note/%5B%20Retn%20BGP-communities%20%5D",
      query: { group: "team" },
      hash: "#part",
      replace: true,
    },
  );
});

test("wikilink title trims accidental outer brackets", () => {
  assert.equal(cleanWikiLinkTitle("  Dedi Migration 2026  "), "Dedi Migration 2026");
  assert.equal(cleanWikiLinkTitle(" [ Dedi Migration 2026 ] "), "Dedi Migration 2026");
});
