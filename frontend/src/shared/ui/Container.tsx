import clsx from "clsx";
import { forwardRef } from "react";
import type { HTMLAttributes } from "react";

export const Container = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={clsx("mx-auto w-full max-w-content px-5 sm:px-8 lg:px-10", className)}
        {...props}
      />
    );
  },
);
Container.displayName = "Container";
