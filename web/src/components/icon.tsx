import { ICON_PATHS, type IconName } from "@/lib/icons.generated";

/** A Material Symbols Outlined icon at weight 400, drawn inline. Decorative unless labelled. */
export function Icon({
  name,
  size = 20,
  label,
  className = "",
}: {
  name: IconName;
  size?: number;
  label?: string;
  className?: string;
}) {
  return (
    <svg
      viewBox="0 -960 960 960"
      width={size}
      height={size}
      fill="currentColor"
      className={`shrink-0 ${className}`}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}
