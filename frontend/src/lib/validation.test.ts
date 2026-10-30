import { describe, expect, it } from "vitest";
import { validateRegistrationPassword } from "./validation";

describe("validateRegistrationPassword", () => {
  it("requires a password with at least eight characters", () => {
    expect(validateRegistrationPassword("short", "short")).toBe(
      "Use at least 8 characters for your password."
    );
  });

  it("rejects passwords that do not match", () => {
    expect(validateRegistrationPassword("long-enough", "different")).toBe(
      "The passwords do not match."
    );
  });

  it("accepts matching passwords that meet the minimum length", () => {
    expect(validateRegistrationPassword("long-enough", "long-enough")).toBeNull();
  });
});
