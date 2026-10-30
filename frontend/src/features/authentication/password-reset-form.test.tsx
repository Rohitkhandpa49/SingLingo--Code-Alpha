import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "@/lib/api";
import { PasswordResetForm } from "./password-reset-form";

vi.mock("next/link", () => ({
  default: ({ href, ...props }: ComponentProps<"a">) => <a href={href} {...props} />
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiRequest: vi.fn() };
});

describe("password reset form", () => {
  beforeEach(() => {
    vi.mocked(apiRequest).mockReset();
    window.history.replaceState({}, "", `/reset-password?token=${"a".repeat(43)}`);
  });

  it("submits a matching password with the reset token", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      message: "Password updated. Please sign in."
    });
    const user = userEvent.setup();
    render(<PasswordResetForm />);

    await user.type(screen.getByLabelText("New password"), "another-secure-password");
    await user.type(screen.getByLabelText("Confirm new password"), "another-secure-password");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Password updated. Please sign in."
    );
    expect(apiRequest).toHaveBeenCalledWith(
      "/auth/password-reset/confirm",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          token: "a".repeat(43),
          password: "another-secure-password",
          password_confirmation: "another-secure-password"
        })
      })
    );
  });

  it("rejects mismatched passwords without sending a request", async () => {
    const user = userEvent.setup();
    render(<PasswordResetForm />);

    await user.type(screen.getByLabelText("New password"), "another-secure-password");
    await user.type(screen.getByLabelText("Confirm new password"), "different-password");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(screen.getByRole("alert")).toHaveTextContent("The passwords do not match.");
    expect(apiRequest).not.toHaveBeenCalled();
  });
});
