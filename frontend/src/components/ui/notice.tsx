import type { ReactNode } from "react";
import { Info } from "lucide-react";

export function Notice({
  children,
  title
}: Readonly<{ children: ReactNode; title?: string }>) {
  return (
    <aside className="notice" role="note">
      <Info aria-hidden="true" />
      <div>
        {title ? <strong>{title}</strong> : null}
        <p>{children}</p>
      </div>
    </aside>
  );
}
