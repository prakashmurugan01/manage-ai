import { describe, expect, it } from "vitest";

import { apiErrorMessage, countFrom, listFrom } from "./client.js";

describe("api client helpers", () => {
  it("normalizes paginated and array payloads", () => {
    expect(listFrom({ data: { results: [{ id: 1 }], count: 1 } })).toEqual([{ id: 1 }]);
    expect(listFrom({ data: [{ id: 2 }] })).toEqual([{ id: 2 }]);
    expect(countFrom({ data: { results: [{ id: 1 }], count: 7 } })).toBe(7);
    expect(countFrom({ data: [{ id: 1 }, { id: 2 }] })).toBe(2);
  });

  it("extracts useful API error messages", () => {
    expect(apiErrorMessage({ response: { data: { detail: "Denied" } } })).toBe("Denied");
    expect(apiErrorMessage({ message: "Network Error" })).toContain("Cannot reach the backend API");
  });
});
