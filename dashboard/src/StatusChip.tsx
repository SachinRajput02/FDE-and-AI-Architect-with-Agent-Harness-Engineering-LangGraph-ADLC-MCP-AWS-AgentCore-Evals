import type { Status } from "./api";
import { statusLabels } from "./format";

export function StatusChip({ status }: Readonly<{ status: Status }>) {
  return <span className={`chip chip-${status}`}>{statusLabels[status]}</span>;
}
