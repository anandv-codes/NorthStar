import clsx from "clsx";
import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(
  ({ label, error, id, className, ...props }, ref) => {
    return (
      <label className="block" htmlFor={id}>
        <span className="mb-1.5 block text-sm font-medium text-neutral-800">{label}</span>
        <input
          ref={ref}
          id={id}
          className={clsx(
            "h-11 w-full rounded-xl border border-neutral-300 bg-white px-3.5 text-sm text-neutral-950 placeholder:text-neutral-400 focus:border-neutral-950 focus:outline-none focus:ring-2 focus:ring-neutral-950/10",
            error ? "border-red-400 focus:border-red-500 focus:ring-red-500/10" : "",
            className,
          )}
          {...props}
        />
        {error ? <span className="mt-1.5 block text-xs text-red-600">{error}</span> : null}
      </label>
    );
  },
);
Field.displayName = "Field";
