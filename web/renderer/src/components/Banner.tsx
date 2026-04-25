type BannerProps = {
  position: "top" | "bottom";
};

export const BANNER_TEXT = "UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY";

export function Banner({ position }: BannerProps) {
  return (
    <div className={`banner banner--${position}`} role="note" aria-label={BANNER_TEXT}>
      {BANNER_TEXT}
    </div>
  );
}
