"use client";

import { useCallback, useRef, useState } from "react";
import { UploadCloud, File as FileIcon, X } from "lucide-react";
import { cn, formatNumber } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

interface FileUploadProps {
  accept?: string;
  hint?: string;
  onFile?: (file: File) => void;
}

/** Accessible drag-and-drop uploader with a simulated progress bar. */
export function FileUpload({ accept, hint = "Any scan, email, or source archive", onFile }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);

  const handleFile = useCallback(
    (f: File) => {
      setFile(f);
      setProgress(0);
      onFile?.(f);
      // Simulated upload progress; replace with real XHR/fetch progress events.
      let pct = 0;
      const timer = setInterval(() => {
        pct = Math.min(100, pct + 12);
        setProgress(pct);
        if (pct >= 100) clearInterval(timer);
      }, 120);
    },
    [onFile]
  );

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const f = e.dataTransfer.files?.[0];
          if (f) handleFile(f);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
          dragging ? "border-primary bg-primary/5" : "border-border/70 hover:border-primary/60 hover:bg-accent/40"
        )}
      >
        <div className="grid h-11 w-11 place-items-center rounded-full bg-primary/10 text-primary">
          <UploadCloud className="h-5 w-5" />
        </div>
        <p className="text-sm font-medium">Drag &amp; drop, or click to browse</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
      </div>

      {file && (
        <div className="flex items-center gap-3 rounded-lg border border-border/60 bg-card/60 p-3">
          <FileIcon className="h-4 w-4 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted-foreground">{formatNumber(Math.round(file.size / 1024))} KB</p>
            <Progress value={progress} className="mt-2" />
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => { setFile(null); setProgress(0); }}
            aria-label="Remove file"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
