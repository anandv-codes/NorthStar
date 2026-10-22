import { NavLink, Outlet } from "react-router-dom";
import { Books, Cards, NotePencil } from "@phosphor-icons/react";
import clsx from "clsx";

const TABS = [
  { to: "/app/library/notes", label: "Notes", icon: NotePencil },
  { to: "/app/library/recall", label: "Recall cards", icon: Cards },
];

export function LibraryLayout() {
  return (
    <div className="mx-auto max-w-7xl">
      <header className="border-b border-neutral-200 pb-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-neutral-400">
              <Books size={14} weight="bold" />
              Library
            </p>
            <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-neutral-950">
              Browse everything you've captured
            </h1>
            <p className="mt-1 max-w-2xl text-sm text-neutral-500">
              Revisit notes, find the cards built from them, and manage recall decks with their live stats.
            </p>
          </div>
        </div>

        <nav aria-label="Library sections" className="mt-5 flex gap-2">
          {TABS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "inline-flex h-10 items-center gap-2 rounded-xl border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-950 focus-visible:ring-offset-2",
                  isActive
                    ? "border-neutral-950 bg-neutral-950 text-white"
                    : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50 hover:text-neutral-950",
                )
              }
            >
              <Icon size={16} weight="bold" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}
