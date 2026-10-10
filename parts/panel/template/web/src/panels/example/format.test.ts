import { describe, expect, it } from "vitest";
import { formatCursor, formatValue } from "./format";

describe("formatValue", () => {
  it("rounds fractional numbers to the precision", () => {
    expect(formatValue("3.14159", 2)).toBe("3.14");
  });

  it("keeps integers and text unchanged", () => {
    expect(formatValue("42", 3)).toBe("42");
    expect(formatValue("RUNNING", 3)).toBe("RUNNING");
    expect(formatValue("", 3)).toBe("");
  });
});

describe("formatCursor", () => {
  it("shows Live without a cursor", () => {
    expect(formatCursor(null)).toBe("Live");
    expect(formatCursor(12.5)).toBe("12.500 s");
  });
});
