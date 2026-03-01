import { describe, expect, it } from "vitest"
import { fmt, fmtDate } from "./format"

describe("fmt", () => {
  it("returns plain number below 1K", () => {
    expect(fmt(0)).toBe("0")
    expect(fmt(999)).toBe("999")
  })

  it("formats thousands with K suffix", () => {
    expect(fmt(1_500)).toBe("1.5K")
    expect(fmt(42_000)).toBe("42.0K")
  })

  it("formats millions with M suffix", () => {
    expect(fmt(2_500_000)).toBe("2.5M")
  })
})

describe("fmtDate", () => {
  it("formats a valid ISO string", () => {
    const result = fmtDate("2024-06-15T14:30:00Z")
    // locale-agnostic: just check day number appears
    expect(result).toContain("15")
  })

  it("returns raw string on invalid input", () => {
    expect(fmtDate("not-a-date")).toBe("not-a-date")
    expect(fmtDate("")).toBe("")
  })
})
