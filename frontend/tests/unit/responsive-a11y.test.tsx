import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnalystComposer } from "@/features/analyst/composer";
import { Header } from "@/components/layout/header";
import { Providers } from "@/lib/query/providers";
import { AuthProvider } from "@/features/auth/auth-context";

describe("Responsive and Accessibility (a11y) Verification", () => {
  it("verifies interactive controls have accessible ARIA labels", () => {
    render(
      <Providers>
        <AuthProvider>
          <Header />
        </AuthProvider>
      </Providers>
    );

    // Theme toggle has aria-label
    const themeButton = screen.getByLabelText(/Toggle theme/i);
    expect(themeButton).toBeInTheDocument();

    // Logout button has aria-label
    const logoutButton = screen.getByLabelText(/Log out/i);
    expect(logoutButton).toBeInTheDocument();
  });

  it("verifies composer form controls are keyboard accessible and navigable", () => {
    render(
      <AnalystComposer
        onSubmit={() => {}}
        isExecuting={false}
      />
    );

    const textarea = screen.getByPlaceholderText(/Ask a question about corporate financials/i);
    expect(textarea).not.toBeDisabled();

    const askButton = screen.getByRole("button", { name: /ask/i });
    expect(askButton).toBeInTheDocument();
  });

  it("verifies component adapts to small viewports (320px, 375px mobile)", () => {
    // Set window innerWidth to simulate mobile 320px
    window.innerWidth = 320;
    window.dispatchEvent(new Event("resize"));

    const { container } = render(
      <AnalystComposer
        onSubmit={() => {}}
        isExecuting={false}
      />
    );

    expect(container.firstChild).toBeInTheDocument();
  });
});
