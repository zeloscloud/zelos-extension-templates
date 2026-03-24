import { useExtensionInfo, useZelosBridge } from "@zeloscloud/app-extension-sdk/react";

export function App() {
  const bridge = useZelosBridge();
  const info = useExtensionInfo();

  if (bridge.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Connecting to Zelos…</p>
      </div>
    );
  }

  if (bridge.status === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-destructive">{bridge.error?.message ?? "Failed to connect"}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <div className="w-full max-w-md space-y-4 rounded-xl border bg-card p-8">
        <div>
          <h1 className="text-xl font-semibold">{info?.name ?? "Extension"}</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {info?.id} · v{info?.version}
          </p>
        </div>
        <p className="text-sm text-muted-foreground">
          Edit{" "}
          <code className="rounded border bg-background px-1.5 py-0.5 text-xs font-medium">
            src/App.tsx
          </code>{" "}
          to start building your extension.
        </p>
      </div>
    </div>
  );
}
