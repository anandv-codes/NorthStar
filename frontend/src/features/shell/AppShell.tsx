import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  ChatCircleDots,
  ClockCounterClockwise,
  List,
  SignOut,
  SquaresFour,
  NotePencil,
  X,
} from "@phosphor-icons/react";
import clsx from "clsx";
import { useAuthorization } from "../../shared/auth/useAuthorization";
import { fetchDueCards, fetchSuggestions } from "../../shared/api/httpClient";
import { LogoMark } from "../../shared/ui/Logo";

const NAV_ITEMS = [
  { to: "/app/dashboard", label: "Dashboard", icon: SquaresFour },
  { to: "/app/recall", label: "Recall", icon: ClockCounterClockwise },
  { to: "/app/notes", label: "Note Taker", icon: NotePencil },
  { to: "/app/chat", label: "Ask", icon: ChatCircleDots },
];

export function AppShell() {
  const { userId, logout } = useAuthorization();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [recallCount, setRecallCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const sync = () => {
      Promise.all([fetchDueCards(1), fetchSuggestions(1)])
        .then(([due, suggestions]) => {
          if (!cancelled) setRecallCount(due.total_due + suggestions.total);
        })
        .catch(() => {
          if (!cancelled) setRecallCount(0);
        });
    };
    sync();
    window.addEventListener("focus", sync);
    return () => {
      cancelled = true;
      window.removeEventListener("focus", sync);
    };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-neutral-50 lg:flex">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-lg focus:bg-neutral-950 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white"
      >
        Skip to content
      </a>

      {/* Mobile top bar */}
      <div className="flex items-center justify-between border-b border-neutral-200 bg-white px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2">
          <LogoMark size={22} />
          <span className="font-display text-base font-semibold">NorthStar</span>
        </div>
        <button
          type="button"
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-neutral-900"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
          aria-controls="app-nav"
          onClick={() => setMobileOpen((v) => !v)}
        >
          {mobileOpen ? <X size={20} /> : <List size={20} />}
        </button>
      </div>

      {/* Sidebar */}
      <aside
        className={clsx(
          "z-40 w-full border-b border-neutral-200 bg-white px-4 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:border-b-0 lg:border-r lg:px-5 lg:py-7",
          mobileOpen ? "block" : "hidden lg:flex lg:flex-col",
        )}
      >
        <div className="hidden items-center gap-2 px-1 lg:flex">
          <LogoMark size={24} />
          <span className="font-display text-lg font-semibold">NorthStar</span>
        </div>

        <nav id="app-nav" className="mt-2 flex flex-col gap-1 lg:mt-8">
          {NAV_ITEMS.map((item) => {
            const showBadge = item.to === "/app/recall" && recallCount > 0;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                aria-label={showBadge ? `${item.label}, ${recallCount} waiting` : undefined}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-neutral-950 text-white"
                      : "text-neutral-600 hover:bg-neutral-100 hover:text-neutral-950",
                  )
                }
              >
                <item.icon size={18} weight="bold" />
                <span className="flex-1">{item.label}</span>
                {showBadge ? (
                  <span
                    aria-hidden="true"
                    className="inline-flex min-w-5 items-center justify-center rounded-full bg-accent-600 px-1.5 py-0.5 text-[11px] font-semibold leading-none text-white"
                  >
                    {recallCount > 99 ? "99+" : recallCount}
                  </span>
                ) : null}
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto hidden flex-col gap-3 pt-8 lg:flex">
          <div className="rounded-xl bg-neutral-100 px-3 py-3">
            <p className="truncate text-xs font-medium text-neutral-500">Signed in as</p>
            <p className="truncate text-sm font-semibold text-neutral-950">{userId}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-950"
          >
            <SignOut size={18} />
            Log out
          </button>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="mt-4 flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium text-neutral-500 lg:hidden"
        >
          <SignOut size={18} />
          Log out
        </button>
      </aside>

      <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 outline-none sm:px-6 lg:px-10 lg:py-10">
        <Outlet />
      </main>
    </div>
  );
}
