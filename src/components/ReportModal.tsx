import { useMemo, useRef } from 'react';
import { X, Copy, FileDown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
// html2pdf.js 没有内置 TS 声明，使用 any 兜底
// eslint-disable-next-line @typescript-eslint/no-var-requires
import html2pdf from 'html2pdf.js';

type ReportModalProps = {
  open: boolean;
  title?: string;
  content: string;
  onClose: () => void;
};

export default function ReportModal({ open, title = 'AI 分析报告', content, onClose }: ReportModalProps) {
  const contentRef = useRef<HTMLDivElement | null>(null);
  const fileName = useMemo(() => `${title.replace(/\s+/g, '_') || 'report'}.pdf`, [title]);

  if (!open) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
    } catch (err) {
      console.error('[ReportModal] 复制失败', err);
    }
  };

  const handleExportPdf = () => {
    if (!contentRef.current) return;
    const opt = {
      margin: 0.5,
      filename: fileName,
      html2canvas: { scale: 2 },
      jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' },
    };
    html2pdf().from(contentRef.current).set(opt).save();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
      <div className="relative w-full max-w-6xl h-[90vh] bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
          <div className="text-lg font-semibold text-slate-900">{title}</div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm font-semibold bg-white text-slate-700 border border-slate-200 hover:bg-slate-100 transition"
              onClick={handleCopy}
            >
              <Copy className="w-4 h-4" />
              复制内容
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-sm font-semibold bg-slate-900 text-white border border-slate-900 hover:bg-slate-800 transition"
              onClick={handleExportPdf}
            >
              <FileDown className="w-4 h-4" />
              导出 PDF
            </button>
            <button
              type="button"
              className="w-9 h-9 inline-flex items-center justify-center rounded-full bg-white border border-slate-200 text-slate-500 hover:bg-slate-100 transition"
              onClick={onClose}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-8 py-6">
          <div ref={contentRef} className="prose prose-slate max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        </div>
      </div>
    </div>
  );
}
