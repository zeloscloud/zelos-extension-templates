import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@zeloscloud/app-extension-sdk/react", () => ({
  useExtensionInfo: () => ({
    id: "local.test-app",
    name: "Test App",
    version: "0.1.0",
  }),
  useZelosBridge: () => ({
    status: "ready",
  }),
}));

import { App } from "./App";

describe("App", () => {
  it("renders extension information", () => {
    render(<App />);

    expect(screen.getByText("Test App")).toBeInTheDocument();
    expect(screen.getByText("local.test-app · v0.1.0")).toBeInTheDocument();
  });
});
