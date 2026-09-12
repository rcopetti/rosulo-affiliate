import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, ZoomIn, ZoomOut } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist/build/pdf.mjs';
import workerSrc from 'pdfjs-dist/build/pdf.worker.mjs?url';
import { Button } from './Button';

pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;

interface PdfViewerProps {
  url: string;
  title?: string;
  className?: string;
}

export function PdfViewer({ url, title = 'PDF preview', className }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pageCount, setPageCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [scale, setScale] = useState(1.15);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let document: pdfjsLib.PDFDocumentProxy | null = null;

    const load = async () => {
      setLoading(true);
      setError(null);
      setCurrentPage(1);
      try {
        document = await pdfjsLib.getDocument(url).promise;
        if (cancelled) return;
        setPageCount(document.numPages);
        const container = containerRef.current;
        if (!container) return;
        container.replaceChildren();

        for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
          const page = await document.getPage(pageNumber);
          if (cancelled) return;
          const viewport = page.getViewport({ scale });
          const canvas = window.document.createElement('canvas');
          canvas.className = 'mx-auto mb-4 block max-w-full shadow-sm';
          canvas.setAttribute('aria-label', `${title}, page ${pageNumber}`);
          canvas.oncontextmenu = (event) => event.preventDefault();
          const context = canvas.getContext('2d');
          if (!context) continue;
          const deviceScale = window.devicePixelRatio || 1;
          canvas.width = Math.floor(viewport.width * deviceScale);
          canvas.height = Math.floor(viewport.height * deviceScale);
          canvas.style.width = `${viewport.width}px`;
          canvas.style.height = `${viewport.height}px`;
          container.appendChild(canvas);
          await page.render({
            canvasContext: context,
            viewport,
            transform: deviceScale !== 1 ? [deviceScale, 0, 0, deviceScale, 0, 0] : undefined,
          }).promise;
        }
      } catch {
        if (!cancelled) setError('Unable to render this PDF. Please try again.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
      void document?.destroy();
    };
  }, [url, scale, title]);

  const scrollToPage = (page: number) => {
    const container = containerRef.current;
    const target = container?.children.item(page - 1) as HTMLElement | null;
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setCurrentPage(page);
  };

  return (
    <div className={className} onContextMenu={(event) => event.preventDefault()}>
      <div className="flex items-center justify-between gap-2 border-b border-line bg-surface-muted px-3 py-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => scrollToPage(Math.max(1, currentPage - 1))} disabled={currentPage <= 1} aria-label="Previous page">
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="min-w-20 text-center text-xs tabular-nums text-fg-muted">
            {pageCount ? `${currentPage} / ${pageCount}` : '—'}
          </span>
          <Button variant="ghost" size="icon" onClick={() => scrollToPage(Math.min(pageCount, currentPage + 1))} disabled={!pageCount || currentPage >= pageCount} aria-label="Next page">
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={() => setScale((value) => Math.max(0.75, value - 0.15))} aria-label="Zoom out">
            <ZoomOut className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="w-12 text-center text-xs tabular-nums text-fg-muted">{Math.round(scale * 100)}%</span>
          <Button variant="ghost" size="icon" onClick={() => setScale((value) => Math.min(2.5, value + 0.15))} aria-label="Zoom in">
            <ZoomIn className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
      <div className="relative max-h-[32rem] overflow-auto bg-slate-700/70 p-4" aria-label={title}>
        <div ref={containerRef} />
        {loading && <div className="absolute inset-0 flex h-48 items-center justify-center gap-2 text-sm text-white"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Loading PDF…</div>}
        {error && <p className="absolute inset-0 p-8 text-center text-sm text-danger-fg">{error}</p>}
      </div>
    </div>
  );
}
