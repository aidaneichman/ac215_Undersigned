import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import App from "./App.jsx";

// fetch is faked, so the tests need no API. ROUTES maps each /api path to [status, body];
// a path that is not listed rejects the way fetch does when the server is down.
let ROUTES;

beforeEach(() => {
  ROUTES = {
    "/api/health": [200, { status: "ok", passages: 538, dockets: ["EPA-HQ-OW-2018-0149"] }],
    "/api/rules/EPA-HQ-OW-2018-0149/sections": [200, { docket_id: "EPA-HQ-OW-2018-0149", sections: SECTIONS }],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url) => {
      if (!(url in ROUTES)) throw new TypeError("Failed to fetch");
      const [status, body] = ROUTES[url];
      return { ok: status < 400, status, statusText: "", json: async () => body };
    }),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

// Same fields as GET /rules/{docket}/sections, taken from the real response for the 2019 rule.
function section(section_ref, title, depth, page, rule_passages) {
  return {
    document_number: "2019-00791",
    citation: "84 FR 4154",
    section_ref,
    parent_ref: section_ref.split("/").slice(0, -1).join("/") || null,
    heading: title,
    title,
    depth,
    page,
    rule_passages,
    citing_passages: null,
    citing_letters: null,
  };
}

const SECTIONS = [
  section("II", "II. Background", 1, 4155, 120),
  section("II/A", "A. Executive Summary", 2, 4155, 6),
  section("II/B", "B. The Clean Water Act and Regulatory Definition", 2, 4156, 51),
  section("II/B/1", "1. The Clean Water Act", 3, 4156, 14),
];

// Each body row as its cell texts: title, page, rule passages, citing passages, citing letters.
async function tableRows() {
  const table = await screen.findByRole("table");
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell").map((cell) => cell.textContent));
}

test("lists the sections of the first indexed docket in reading order", async () => {
  render(<App />);
  const rows = await tableRows();
  expect(rows.map((r) => r[0])).toEqual([
    "II. Background",
    "A. Executive Summary",
    "B. The Clean Water Act and Regulatory Definition",
    "1. The Clean Water Act",
  ]);
  expect(rows[0].slice(1, 3)).toEqual(["4155", "120"]);
  expect(screen.getByText("Rules / EPA-HQ-OW-2018-0149")).toBeTruthy();
  expect(screen.getByText("4 sections from 84 FR 4154")).toBeTruthy();
});

test("says it is loading until the sections arrive", async () => {
  render(<App />);
  expect(screen.getByText("Loading sections…")).toBeTruthy();
  await screen.findByRole("table");
  expect(screen.queryByText("Loading sections…")).toBeNull();
});

test("indents each section by its depth", async () => {
  render(<App />);
  await screen.findByRole("table");
  const indent = (title) => screen.getByText(title).style.marginLeft;
  expect(indent("II. Background")).toBe("0rem");
  expect(indent("A. Executive Summary")).toBe("1.25rem");
  expect(indent("1. The Clean Water Act")).toBe("2.5rem");
});

test("shows unknown citing counts as a dash, not zero, and explains it", async () => {
  render(<App />);
  const rows = await tableRows();
  expect(rows[0].slice(3)).toEqual(["—", "—"]);
  expect(screen.getByText(/— means not counted yet/)).toBeTruthy();
});

test("shows citing counts once the API has them", async () => {
  const counted = SECTIONS.map((s) => ({ ...s, citing_passages: 1234, citing_letters: 0 }));
  ROUTES["/api/rules/EPA-HQ-OW-2018-0149/sections"][1].sections = counted;
  render(<App />);
  const rows = await tableRows();
  expect(rows[0].slice(3)).toEqual(["1,234", "0"]);
  expect(screen.queryByText(/— means not counted yet/)).toBeNull();
});

test("?docket= picks the rule without asking /health", async () => {
  window.history.replaceState(null, "", "/?docket=EPA-HQ-OW-2022-0801");
  ROUTES["/api/rules/EPA-HQ-OW-2022-0801/sections"] = [
    200,
    { docket_id: "EPA-HQ-OW-2022-0801", sections: [section("I", "I. General Information", 1, 10, 3)] },
  ];
  render(<App />);
  expect((await tableRows()).map((r) => r[0])).toEqual(["I. General Information"]);
  expect(fetch.mock.calls.map(([url]) => url)).not.toContain("/api/health");
});

test("shows the API's reason for an unknown docket", async () => {
  window.history.replaceState(null, "", "/?docket=NOPE");
  const detail = "No rule text indexed for docket 'NOPE'. Indexed: EPA-HQ-OW-2018-0149";
  ROUTES["/api/rules/NOPE/sections"] = [404, { detail }];
  render(<App />);
  expect(await screen.findByText(detail)).toBeTruthy();
  expect(screen.queryByRole("table")).toBeNull();
});

test("says so when the API cannot be reached", async () => {
  delete ROUTES["/api/health"];
  render(<App />);
  expect(await screen.findByText("The API cannot be reached.")).toBeTruthy();
});

test("says so when the API has no rule indexed", async () => {
  ROUTES["/api/health"][1].dockets = [];
  render(<App />);
  expect(await screen.findByText("The API has no rule text indexed yet.")).toBeTruthy();
});

test("says so when a docket has no sections", async () => {
  ROUTES["/api/rules/EPA-HQ-OW-2018-0149/sections"][1].sections = [];
  render(<App />);
  expect(await screen.findByText("No sections found for EPA-HQ-OW-2018-0149.")).toBeTruthy();
});
