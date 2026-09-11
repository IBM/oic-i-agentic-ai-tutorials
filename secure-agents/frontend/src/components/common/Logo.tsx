import { cn } from "@/lib/utils";
import { useTheme } from "../theme/ThemeProvider";

interface LogoProps {
  className?: string;
  logoOnly?: boolean;
  logoSize?: "sm" | "md" | "lg";
}

export const Logo = ({
  className,
  logoSize = "md",
  logoOnly = false,
}: LogoProps) => {
  const { actualTheme } = useTheme();

  return (
    <div className={cn("flex items-center justify-center text-xl", className)}>
      <img
        className={cn({
          "w-8": logoSize === "sm",
          "w-12": logoSize === "md",
          "w-16": logoSize === "lg",
        })}
        src={
          actualTheme === "dark"
            ? "/assets/images/ibm-bee-white.png"
            : "/assets/images/ibm-bee-black.png"
        }
        alt="IBM-Client-Engineering"
      />
      {!logoOnly && (
        <p className="pl-2">
          IBM <strong>Client Engineering</strong>
        </p>
      )}
    </div>
  );
};
