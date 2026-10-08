import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const copyText = vi.fn();
const setOptions = vi.fn();
let options = { precision: 2, showProducer: false };

vi.mock("@zeloscloud/app-extension-sdk/react", () => ({
  usePanel: () => ({
    signals: [
      { source: "demo", message: "sensor", signal: "voltage", path: "demo/sensor.voltage" },
    ],
  }),
  useTimeState: () => ({ cursorS: null }),
  usePanelOptions: () => [options, setOptions],
  usePanelActions: () => ({ copyText }),
  usePanelData: () => ({
    latest: [
      { source: "demo", message: "sensor", signal: "voltage", value: "3.14159", producer: "bench" },
    ],
  }),
}));

import { ExamplePanel } from "./ExamplePanel";

describe("ExamplePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    options = { precision: 2, showProducer: false };
  });

  it("shows the latest value of each bound signal at the chosen precision", () => {
    render(<ExamplePanel />);

    expect(screen.getByText("sensor.voltage")).toBeInTheDocument();
    expect(screen.getByText("3.14")).toBeInTheDocument();
    expect(screen.queryByText("bench")).not.toBeInTheDocument();
  });

  it("copies the full value on click", () => {
    render(<ExamplePanel />);

    fireEvent.click(screen.getByText("3.14"));
    expect(copyText).toHaveBeenCalledWith("3.14159", "Value copied");
  });

  it("saves the producer option and shows the column when it is on", () => {
    const { rerender } = render(<ExamplePanel />);

    fireEvent.click(screen.getByLabelText("Show producer"));
    expect(setOptions).toHaveBeenCalledWith({ showProducer: true });

    options = { precision: 2, showProducer: true };
    rerender(<ExamplePanel />);
    expect(screen.getByText("bench")).toBeInTheDocument();
  });
});
