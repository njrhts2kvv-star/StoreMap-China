import type { ReactNode, ButtonHTMLAttributes } from 'react';

const cx = (...args: Array<string | false | undefined>) => args.filter(Boolean).join(' ');

type CardProps = { children: ReactNode; className?: string; onClick?: () => void };
export function Card({ children, className, onClick }: CardProps) {
  return <div className={cx('rounded-[28px] bg-white shadow-[0_14px_40px_rgba(15,23,42,0.08)] border border-white/60', className)} onClick={onClick}>{children}</div>;
}

type BadgeProps = { children: ReactNode; tone?: 'dji' | 'insta' | 'neutral'; className?: string };
export function Badge({ children, tone = 'neutral', className }: BadgeProps) {
  const toneClass =
    tone === 'dji'
      ? 'bg-brand-dji/15 text-brand-dji'
      : tone === 'insta'
        ? 'bg-yellow-100 text-amber-700'
        : 'bg-slate-100 text-slate-700';
  return <span className={cx('inline-flex items-center px-3 py-1.5 rounded-full text-[11px] font-semibold tracking-tight', toneClass, className)}>{children}</span>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'outline' };
export function Button({ children, className, variant = 'primary', ...rest }: ButtonProps) {
  const base = 'rounded-full px-4 py-2.5 text-sm font-semibold active:scale-95 transition shadow-md';
  const map = {
    primary: 'bg-slate-900 text-white hover:brightness-95',
    ghost: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    outline: 'border border-slate-200 text-slate-700 bg-white hover:border-slate-300',
  };
  return (
    <button className={cx(base, map[variant], className)} {...rest}>
      {children}
    </button>
  );
}
