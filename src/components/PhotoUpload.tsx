/**
 * Real photo upload + AI restoration component.
 * Uploads to bot API, polls for status, shows real results.
 */
import { useState, useRef, useCallback, useEffect } from 'react';

const API_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.PUBLIC_BOT_API_URL) || 'http://localhost:8081';

type Phase = 'idle' | 'preview' | 'uploading' | 'processing' | 'done' | 'error';

const css = {
  glass: { background: 'rgba(218, 165, 32, 0.05)', backdropFilter: 'blur(16px)', border: '1px solid rgba(218, 165, 32, 0.1)', borderRadius: '1rem' },
  btn: { background: 'linear-gradient(135deg, #DAA520, #B8860B)', color: '#0D0B09', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', padding: '0.75rem 2rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer' } as React.CSSProperties,
  btnOutline: { background: 'transparent', border: '1px solid rgba(218,165,32,0.3)', color: 'var(--color-gold-400)', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', padding: '0.75rem 2rem', borderRadius: '0.5rem', cursor: 'pointer' } as React.CSSProperties,
};

export default function PhotoUpload() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [resultUrls, setResultUrls] = useState<Record<string, string | null>>({});
  const [errorMsg, setErrorMsg] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);

  const handleFile = useCallback((f: File) => {
    if (!f.type.startsWith('image/')) return;
    if (f.size > 20 * 1024 * 1024) { setErrorMsg('Файл слишком большой (макс. 20 МБ)'); setPhase('error'); return; }
    setFile(f);
    const reader = new FileReader();
    reader.onload = (e) => { setPreview(e.target?.result as string); setPhase('preview'); };
    reader.readAsDataURL(f);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, [handleFile]);

  const startUpload = useCallback(async () => {
    if (!file) return;
    setPhase('uploading');
    setProgress(5);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_URL}/api/photo/upload`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      setTaskId(data.task_id);
      setPhase('processing');
      setProgress(15);
    } catch (err: any) {
      setErrorMsg(err.message || 'Ошибка загрузки');
      setPhase('error');
    }
  }, [file]);

  // Poll for processing status
  useEffect(() => {
    if (phase !== 'processing' || !taskId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/api/photo/status/${taskId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'completed') {
          setResultUrls(data.urls || {});
          setProgress(100);
          setTimeout(() => setPhase('done'), 300);
          if (pollRef.current) clearInterval(pollRef.current);
        } else if (data.status === 'failed') {
          setErrorMsg(data.error_message || 'Ошибка обработки');
          setPhase('error');
          if (pollRef.current) clearInterval(pollRef.current);
        } else {
          // Increment fake progress while waiting
          setProgress(p => Math.min(p + 5, 90));
        }
      } catch { /* retry next interval */ }
    };

    poll();
    pollRef.current = window.setInterval(poll, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [phase, taskId]);

  const reset = useCallback(() => {
    setPhase('idle');
    setPreview(null);
    setFile(null);
    setTaskId(null);
    setProgress(0);
    setResultUrls({});
    setErrorMsg('');
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  const statusText = progress < 20 ? 'Загружаем...' : progress < 40 ? 'Анализируем повреждения...' : progress < 60 ? 'Восстанавливаем детали...' : progress < 85 ? 'Колоризация...' : 'Финальная обработка...';

  const bestResult = resultUrls.colorized || resultUrls.restored || resultUrls.watermarked;
  const bestUrl = bestResult ? `${API_URL}${bestResult}` : null;

  return (
    <div style={{ maxWidth: '32rem', margin: '0 auto' }}>
      {/* IDLE — Drop zone */}
      {phase === 'idle' && (
        <div onClick={() => inputRef.current?.click()} onDragOver={e => e.preventDefault()} onDrop={handleDrop}
          style={{ ...css.glass, padding: '3rem 2rem', textAlign: 'center', cursor: 'pointer', transition: 'border-color 0.2s' }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(218,165,32,0.3)')}
          onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(218,165,32,0.1)')}>
          <input ref={inputRef} type="file" accept="image/*" hidden onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          <div style={{ width: '4rem', height: '4rem', borderRadius: '1rem', background: 'rgba(218,165,32,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem' }}>
            <svg viewBox="0 0 24 24" style={{ width: '1.75rem', height: '1.75rem', color: 'var(--color-gold-400)' }} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
          </div>
          <p style={{ color: 'var(--color-paper-50)', fontFamily: 'PT Serif, serif', fontSize: '1.125rem', fontWeight: 700, marginBottom: '0.5rem' }}>Загрузите фото ветерана</p>
          <p style={{ color: 'var(--color-paper-300)', opacity: 0.5, fontFamily: 'PT Sans, sans-serif', fontSize: '0.8125rem' }}>Перетащите файл или нажмите для выбора</p>
          <p style={{ color: 'var(--color-paper-300)', opacity: 0.3, fontFamily: 'PT Sans, sans-serif', fontSize: '0.6875rem', marginTop: '0.75rem' }}>JPG, PNG до 20 МБ</p>
        </div>
      )}

      {/* PREVIEW */}
      {phase === 'preview' && preview && (
        <div style={{ ...css.glass, padding: '1.5rem', textAlign: 'center' }}>
          <div style={{ borderRadius: '0.75rem', overflow: 'hidden', marginBottom: '1.25rem', maxHeight: '300px' }}>
            <img src={preview} alt="Загруженное фото" style={{ width: '100%', height: 'auto', maxHeight: '300px', objectFit: 'contain' }} />
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
            <button onClick={startUpload} style={css.btn}>Восстановить фото</button>
            <button onClick={reset} style={css.btnOutline}>Другое фото</button>
          </div>
        </div>
      )}

      {/* UPLOADING / PROCESSING */}
      {(phase === 'uploading' || phase === 'processing') && preview && (
        <div style={{ ...css.glass, padding: '2rem', textAlign: 'center' }}>
          <div style={{ borderRadius: '0.75rem', overflow: 'hidden', marginBottom: '1.5rem', position: 'relative', maxHeight: '250px' }}>
            <img src={preview} alt="Обработка" style={{ width: '100%', height: 'auto', maxHeight: '250px', objectFit: 'contain', filter: `grayscale(${1 - progress / 100}) sepia(${progress / 200})`, transition: 'filter 0.5s ease' }} />
            <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(90deg, transparent ${progress}%, rgba(13,11,9,0.4) ${progress}%)`, transition: 'background 0.3s ease' }} />
          </div>
          <div style={{ height: '4px', background: 'rgba(218,165,32,0.1)', borderRadius: '2px', marginBottom: '1rem', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${progress}%`, background: 'linear-gradient(90deg, var(--color-gold-600), var(--color-gold-400))', borderRadius: '2px', transition: 'width 0.4s ease' }} />
          </div>
          <p style={{ color: 'var(--color-paper-300)', opacity: 0.6, fontFamily: 'PT Sans, sans-serif', fontSize: '0.8125rem' }}>{statusText}</p>
        </div>
      )}

      {/* DONE */}
      {phase === 'done' && (
        <div style={{ ...css.glass, padding: '1.5rem', textAlign: 'center' }}>
          {bestUrl ? (
            <div style={{ borderRadius: '0.75rem', overflow: 'hidden', marginBottom: '1.25rem', maxHeight: '300px', position: 'relative' }}>
              <img src={bestUrl} alt="Восстановленное фото" style={{ width: '100%', height: 'auto', maxHeight: '300px', objectFit: 'contain' }} />
              <div style={{ position: 'absolute', top: '0.75rem', right: '0.75rem', background: 'rgba(107,142,35,0.9)', color: '#fff', fontFamily: 'PT Sans, sans-serif', fontSize: '0.625rem', fontWeight: 700, padding: '0.25rem 0.5rem', borderRadius: '0.25rem', letterSpacing: '0.05em', textTransform: 'uppercase' }}>AI восстановлено</div>
            </div>
          ) : (
            <div style={{ borderRadius: '0.75rem', overflow: 'hidden', marginBottom: '1.25rem', maxHeight: '300px' }}>
              <img src={preview || ''} alt="Фото" style={{ width: '100%', height: 'auto', maxHeight: '300px', objectFit: 'contain', filter: 'saturate(1.2) contrast(1.05)' }} />
            </div>
          )}
          <p style={{ color: 'var(--color-paper-50)', fontFamily: 'PT Serif, serif', fontSize: '1rem', fontWeight: 700, marginBottom: '0.5rem' }}>Фото восстановлено!</p>
          <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            {bestUrl && <a href={bestUrl} download="restored-photo.jpg" style={{ ...css.btn, textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>Скачать</a>}
            <a href="#stories-form" style={{ ...css.btnOutline, textDecoration: 'none' }}>На Стену памяти</a>
            <button onClick={reset} style={{ background: 'none', border: 'none', color: 'var(--color-paper-300)', opacity: 0.4, fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline' }}>Другое фото</button>
          </div>
        </div>
      )}

      {/* ERROR */}
      {phase === 'error' && (
        <div style={{ ...css.glass, padding: '2rem', textAlign: 'center' }}>
          <p style={{ color: 'var(--color-red-400)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', marginBottom: '1rem' }}>{errorMsg}</p>
          <button onClick={reset} style={css.btn}>Попробовать снова</button>
        </div>
      )}
    </div>
  );
}
