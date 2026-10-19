import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "../../shared/ui/Logo";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-neutral-950 p-12 text-white lg:flex">
        <Link to="/" className="inline-flex items-center gap-2">
          <LogoMark size={26} className="text-white" />
          <span className="font-display text-lg font-semibold">NorthStar</span>
        </Link>

        <div className="max-w-sm">
          <p className="font-display text-3xl font-semibold leading-snug">
            “NorthStar turned three months of scattered meeting notes into a
            dashboard I actually check every morning.”
          </p>
          <p className="mt-6 text-sm text-neutral-400">Early user, Product team</p>
        </div>

        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-accent-600/20 blur-3xl"
        />
      </div>

      <div className="flex items-center justify-center px-5 py-12 sm:px-10">
        <div className="w-full max-w-sm">
          <Link to="/" className="mb-10 inline-flex items-center gap-2 lg:hidden" aria-label="NorthStar home">
            <LogoMark size={24} />
            <span className="font-display text-lg font-semibold">NorthStar</span>
          </Link>

          <h1 className="font-display text-2xl font-semibold tracking-tight text-neutral-950">{title}</h1>
          <p className="mt-2 text-sm text-neutral-500">{subtitle}</p>

          <div className="mt-8">{children}</div>
          <div className="mt-8 text-center text-sm text-neutral-500">{footer}</div>
        </div>
      </div>
    </div>
  );
}
