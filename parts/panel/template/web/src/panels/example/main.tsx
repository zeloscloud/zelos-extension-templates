import type { AppBridgePanelSignal } from "@zeloscloud/app-extension-sdk";
import { ZelosBridgeProvider } from "@zeloscloud/app-extension-sdk/react";
import React from "react";
import ReactDOM from "react-dom/client";
import { ExamplePanel } from "./ExamplePanel";
import "../../index.css";

// `npm run dev` has no Zelos host: the SDK mounts this page as a mock panel bound to these signals.
const DEV_SIGNALS: AppBridgePanelSignal[] = [
  {
    source: "demo",
    message: "sensor",
    signal: "voltage",
    path: "demo/sensor.voltage",
    unit: "V",
    color: "#3b82f6",
  },
  {
    source: "demo",
    message: "sensor",
    signal: "current",
    path: "demo/sensor.current",
    unit: "A",
    color: "#f97316",
  },
];

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Missing #root element");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ZelosBridgeProvider
      connectOptions={
        import.meta.env.DEV
          ? {
              panel: { panelId: "example", instanceId: "dev", signals: DEV_SIGNALS },
              time: { playback: "LIVE", cursorS: null, viewRange: null },
            }
          : undefined
      }
    >
      <ExamplePanel />
    </ZelosBridgeProvider>
  </React.StrictMode>,
);
