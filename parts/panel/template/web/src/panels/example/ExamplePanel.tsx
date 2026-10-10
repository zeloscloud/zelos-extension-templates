import {
  usePanel,
  usePanelActions,
  usePanelData,
  usePanelOptions,
  useTimeState,
} from "@zeloscloud/app-extension-sdk/react";
import { formatCursor, formatValue } from "./format";

// Defaults for the options declared in web/public/panels/example.options.json.
const DEFAULT_OPTIONS = { precision: 3, showProducer: false };

const CELL = "border-b px-2 py-1 text-left whitespace-nowrap";

function Message({ children, error = false }: { children: string; error?: boolean }) {
  return (
    <div className="flex h-full items-center justify-center p-4 text-center">
      <p className={error ? "text-destructive" : "text-muted-foreground"}>{children}</p>
    </div>
  );
}

export function ExamplePanel() {
  const panel = usePanel();
  const time = useTimeState();
  const [options, setOptions] = usePanelOptions(DEFAULT_OPTIONS);
  const actions = usePanelActions();
  const bound = panel?.signals ?? [];
  // One subscription for the latest value of every bound signal. The host pushes a new
  // frame when a value changes; the SDK acknowledges each frame.
  const data = usePanelData(bound.length > 0 ? { id: "latest", shape: "latest" } : null);

  if (!panel) {
    return <Message>Connecting to Zelos…</Message>;
  }

  if (bound.length === 0) {
    return <Message>Drop signals here, or bind them in the panel's Edit sheet.</Message>;
  }

  const rows = data?.latest ?? [];

  return (
    <div className="flex h-full flex-col text-xs">
      <div className="flex items-center justify-between gap-2 border-b px-2 py-1.5">
        <span className="text-muted-foreground">Cursor: {formatCursor(time?.cursorS ?? null)}</span>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={options.showProducer}
            onChange={(event) => void setOptions({ showProducer: event.target.checked })}
          />
          Show producer
        </label>
      </div>
      <div className="flex-1 overflow-auto">
        {data?.error ? (
          <Message error>{data.error}</Message>
        ) : (
          <table className="w-full border-collapse">
            <thead className="sticky top-0 bg-background text-muted-foreground">
              <tr>
                <th className={`${CELL} font-medium`}>Signal</th>
                <th className={`${CELL} font-medium`}>Value</th>
                {options.showProducer && <th className={`${CELL} font-medium`}>Producer</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.source}/${row.message}.${row.signal}@${row.producer ?? ""}`}
                  className="cursor-pointer hover:bg-accent"
                  title="Click to copy the value"
                  onClick={() => void actions.copyText(row.value, "Value copied")}
                >
                  <td className={CELL}>
                    {row.message}.{row.signal}
                  </td>
                  <td className={`${CELL} tabular-nums`}>
                    {formatValue(row.value, options.precision)}
                  </td>
                  {options.showProducer && (
                    <td className={`${CELL} text-muted-foreground`}>{row.producer ?? "—"}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data?.isLoading && rows.length === 0 && <Message>Loading…</Message>}
      </div>
    </div>
  );
}
