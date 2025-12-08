type SectionHeaderProps = {
  title: string;
  description?: string;
};

export function SectionHeader({ title, description }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="text-base font-semibold text-neutral-10">{title}</div>
        {description && <div className="text-xs text-neutral-5 mt-0.5">{description}</div>}
      </div>
    </div>
  );
}

