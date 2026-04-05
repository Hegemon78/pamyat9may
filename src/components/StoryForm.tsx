/**
 * Story submission form — posts directly to bot API.
 * Works on the website without Telegram.
 */
import { useState, useCallback } from 'react';

type Phase = 'form' | 'sending' | 'success';

const API_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.PUBLIC_BOT_API_URL) || 'http://localhost:8081';

const css = {
  glass: { background: 'rgba(218, 165, 32, 0.05)', backdropFilter: 'blur(16px)', border: '1px solid rgba(218, 165, 32, 0.1)', borderRadius: '1rem', padding: 'clamp(1.5rem, 3vw, 2rem)' },
  input: { width: '100%', background: 'rgba(250,243,232,0.06)', border: '1px solid rgba(218,165,32,0.12)', borderRadius: '0.5rem', padding: '0.75rem 1rem', color: 'var(--color-paper-100)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', outline: 'none', transition: 'border-color 0.2s' },
  btn: { background: 'linear-gradient(135deg, #DAA520, #B8860B)', color: '#0D0B09', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', padding: '0.75rem 2rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer', width: '100%' },
  label: { display: 'block', color: 'var(--color-paper-300)', opacity: 0.6, fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem', marginBottom: '0.375rem' },
};

export default function StoryForm() {
  const [phase, setPhase] = useState<Phase>('form');
  const [heroName, setHeroName] = useState('');
  const [text, setText] = useState('');
  const [authorName, setAuthorName] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) { setError('Расскажите историю вашего героя'); return; }
    setError('');
    setPhase('sending');

    try {
      const res = await fetch(`${API_URL}/api/stories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hero_name: heroName.trim() || undefined,
          text: text.trim(),
          author_name: authorName.trim() || undefined,
        }),
      });
      if (res.ok) {
        setPhase('success');
      } else {
        throw new Error('Ошибка сервера');
      }
    } catch {
      setPhase('form');
      setError('Не удалось отправить. Попробуйте позже или отправьте через Telegram-бот.');
    }
  }, [heroName, text, authorName]);

  const reset = useCallback(() => {
    setPhase('form');
    setHeroName('');
    setText('');
    setAuthorName('');
    setError('');
  }, []);

  return (
    <section style={{ padding: 'clamp(3rem, 6vw, 6rem) 0', backgroundColor: 'var(--color-bg-800)' }} id="stories-form">
      <div style={{ maxWidth: '36rem', margin: '0 auto', padding: '0 1rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <span style={{ color: 'var(--color-gold-500)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
            Стена памяти
          </span>
          <h2 style={{ color: 'var(--color-paper-50)', fontSize: 'clamp(1.875rem, 4vw, 3rem)', fontFamily: 'Playfair Display, serif', fontWeight: 700, marginBottom: '0.5rem' }}>
            Расскажите о своём герое
          </h2>
          <p style={{ color: 'var(--color-paper-300)', opacity: 0.5, fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', maxWidth: '28rem', margin: '0 auto' }}>
            Каждая история важна. Ваш рассказ появится на Стене памяти и сохранит подвиг навсегда.
          </p>
        </div>

        {phase === 'form' && (
          <form onSubmit={handleSubmit} style={css.glass}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={css.label}>Имя героя</label>
              <input
                type="text"
                value={heroName}
                onChange={e => setHeroName(e.target.value)}
                placeholder="Иванов Пётр Сергеевич"
                style={css.input}
                onFocus={e => (e.target.style.borderColor = 'rgba(218,165,32,0.3)')}
                onBlur={e => (e.target.style.borderColor = 'rgba(218,165,32,0.12)')}
              />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={css.label}>История <span style={{ color: 'var(--color-red-400)' }}>*</span></label>
              <textarea
                value={text}
                onChange={e => setText(e.target.value)}
                placeholder="Расскажите о подвиге, о жизни, о том, каким вы запомнили вашего героя..."
                rows={5}
                style={{ ...css.input, resize: 'vertical', minHeight: '120px', lineHeight: 1.6 }}
                onFocus={e => (e.target.style.borderColor = 'rgba(218,165,32,0.3)')}
                onBlur={e => (e.target.style.borderColor = 'rgba(218,165,32,0.12)')}
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={css.label}>Ваше имя</label>
              <input
                type="text"
                value={authorName}
                onChange={e => setAuthorName(e.target.value)}
                placeholder="Мария И."
                style={css.input}
                onFocus={e => (e.target.style.borderColor = 'rgba(218,165,32,0.3)')}
                onBlur={e => (e.target.style.borderColor = 'rgba(218,165,32,0.12)')}
              />
            </div>
            {error && (
              <p style={{ color: 'var(--color-red-400)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem', marginBottom: '1rem' }}>
                {error}
              </p>
            )}
            <button type="submit" style={css.btn}>
              Опубликовать историю
            </button>
          </form>
        )}

        {phase === 'sending' && (
          <div style={{ ...css.glass, textAlign: 'center', padding: '3rem 2rem' }}>
            <div style={{ width: '3rem', height: '3rem', border: '3px solid rgba(218,165,32,0.2)', borderTopColor: 'var(--color-gold-400)', borderRadius: '50%', margin: '0 auto 1.5rem', animation: 'spin 1s linear infinite' }} />
            <p style={{ color: 'var(--color-paper-300)', opacity: 0.6, fontFamily: 'PT Sans, sans-serif' }}>
              Отправляем историю...
            </p>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

        {phase === 'success' && (
          <div style={{ ...css.glass, textAlign: 'center', padding: '3rem 2rem' }}>
            <div style={{ width: '3.5rem', height: '3.5rem', borderRadius: '50%', background: 'rgba(107,142,35,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem' }}>
              <svg viewBox="0 0 24 24" style={{ width: '1.5rem', height: '1.5rem', color: 'var(--color-olive-500)' }} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 13l4 4L19 7"/>
              </svg>
            </div>
            <p style={{ color: 'var(--color-paper-50)', fontFamily: 'PT Serif, serif', fontSize: '1.125rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              Спасибо! История опубликована.
            </p>
            <p style={{ color: 'var(--color-paper-300)', opacity: 0.5, fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              Ваша история теперь на Стене памяти. Память жива.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
              <a href="/wall" style={{ ...css.btn, textDecoration: 'none', display: 'inline-block', textAlign: 'center' }}>
                Стена памяти
              </a>
              <button onClick={reset} style={{ ...css.btn, background: 'transparent', border: '1px solid rgba(218,165,32,0.3)', color: 'var(--color-gold-400)' }}>
                Ещё одна история
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
