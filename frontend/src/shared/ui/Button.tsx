import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

const baseClass =
  "inline-flex items-center justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:hover:bg-blue-400";

export const Button = ({
  children,
  className,
  ...props
}: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) => (
  <button className={[baseClass, className].filter(Boolean).join(" ")} {...props}>
    {children}
  </button>
);
