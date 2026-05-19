import assert from "node:assert/strict";
import { test } from "node:test";

import {
  allGroups,
  canonicalizeLegacyGroupQuery,
  cleanNoteTitleForRoute,
  cleanWikiLinkTitle,
  groupQueryValue,
  legacyGroup,
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

test("wikilink title trims accidental outer brackets", () => {
  assert.equal(cleanWikiLinkTitle("  Dedi Migration 2026  "), "Dedi Migration 2026");
  assert.equal(cleanWikiLinkTitle(" [ Dedi Migration 2026 ] "), "Dedi Migration 2026");
});
