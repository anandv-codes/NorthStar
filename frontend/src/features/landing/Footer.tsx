import { Link } from "react-router-dom";
import { Logo } from "../../shared/ui/Logo";
import { Container } from "../../shared/ui/Container";

const COLUMNS = [
  {
    title: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Features", href: "#features" },
      { label: "Pricing", href: "#pricing" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Product areas",
    links: [
      { label: "Dashboard", href: "/register" },
      { label: "Note Taker", href: "/register" },
      { label: "Chat", href: "/register" },
      { label: "Recall", href: "/register" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "Contact", href: "mailto:hello@northstar.app" },
      { label: "Privacy", href: "#" },
      { label: "Terms", href: "#" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-neutral-200 bg-white">
      <Container className="py-14">
        <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <Logo size={24} />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-neutral-500">
              Capture a thought, and let NorthStar turn it into summaries, tasks
              and things worth remembering.
            </p>
          </div>
          {COLUMNS.map((column) => (
            <div key={column.title}>
              <p className="text-xs font-semibold uppercase tracking-[0.15em] text-neutral-400">
                {column.title}
              </p>
              <ul className="mt-4 space-y-3">
                {column.links.map((link) => (
                  <li key={link.label}>
                    {link.href.startsWith("/") ? (
                      <Link
                        to={link.href}
                        className="text-sm text-neutral-600 transition-colors hover:text-neutral-950"
                      >
                        {link.label}
                      </Link>
                    ) : (
                      <a
                        href={link.href}
                        className="text-sm text-neutral-600 transition-colors hover:text-neutral-950"
                      >
                        {link.label}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-neutral-200 pt-6 text-xs text-neutral-400 sm:flex-row">
          <p>© {new Date().getFullYear()} NorthStar. All rights reserved.</p>
          <p>Built for people who think out loud.</p>
        </div>
      </Container>
    </footer>
  );
}
