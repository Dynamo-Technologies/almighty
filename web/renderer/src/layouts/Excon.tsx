import type { ReactNode } from "react";

type ExconProps = {
  sidebar: ReactNode;
  map: ReactNode;
  actions: ReactNode;
};

export function Excon({ sidebar, map, actions }: ExconProps) {
  return (
    <div className="excon">
      <aside className="excon__sidebar">{sidebar}</aside>
      <section className="excon__map">{map}</section>
      <aside className="excon__actions">{actions}</aside>
    </div>
  );
}
