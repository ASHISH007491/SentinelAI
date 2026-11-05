import { icons, type LucideProps } from "lucide-react";

interface IconProps extends LucideProps {
  name: keyof typeof icons;
}

/** Render a lucide icon by name. Falls back to nothing if the name is unknown. */
export function Icon({ name, ...props }: IconProps) {
  const LucideIcon = icons[name];
  if (!LucideIcon) return null;
  return <LucideIcon {...props} />;
}
