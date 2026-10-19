import clsx from "clsx";

interface LogoProps {
  className?: string;
  markClassName?: string;
  size?: number;
  withWordmark?: boolean;
}

/**
 * Black & white "northstar" sparkle mark, inspired by the reference icon's silhouette
 * (four-point star) but rendered in a single currentColor so it works on any surface.
 */
export function LogoMark({ className, size = 28 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M16 2C17.1 9.6 18.2 13.8 30 16C18.2 18.2 17.1 22.4 16 30C14.9 22.4 13.8 18.2 2 16C13.8 13.8 14.9 9.6 16 2Z"
        fill="currentColor"
      />
    </svg>
  );
}

export function Logo({ className, markClassName, size = 28, withWordmark = true }: LogoProps) {
  return (
    <span className={clsx("inline-flex items-center gap-2 text-neutral-950", className)}>
      <LogoMark className={clsx("text-neutral-950", markClassName)} size={size} />
      {withWordmark ? (
        <span className="font-display text-lg font-semibold tracking-tight">
          NorthStar
        </span>
      ) : null}
    </span>
  );
}
