/**
 * Interactive WWII Quiz with 3 categories and discount system.
 *
 * TODO: Add timer per question for competitive mode.
 * TODO: Add leaderboard integration with bot API.
 * TODO: Improve answer feedback animations.
 * TODO: Add share result button for social media.
 */
import { useState, useCallback, useMemo } from 'react';
import { categories, type QuizQuestion, type QuizCategory, getDiscount } from '../data/quiz';

type Phase = 'categories' | 'playing' | 'result';

interface ShuffledQ {
  question: string;
  shuffledOptions: string[];
  shuffledCorrectIndex: number;
}

function shuffle(q: QuizQuestion): ShuffledQ {
  const idx = q.options.map((_, i) => i);
  for (let i = idx.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [idx[i], idx[j]] = [idx[j], idx[i]];
  }
  return {
    question: q.question,
    shuffledOptions: idx.map(i => q.options[i]),
    shuffledCorrectIndex: idx.indexOf(q.correctIndex),
  };
}

const css = {
  section: { backgroundColor: 'var(--color-bg-800)', padding: 'clamp(3rem, 6vw, 6rem) 0' } as const,
  container: { maxWidth: '42rem', margin: '0 auto', padding: '0 1rem' } as const,
  label: { color: 'var(--color-gold-500)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase' as const, display: 'block', marginBottom: '0.75rem' },
  heading: { color: 'var(--color-paper-50)', fontSize: 'clamp(1.875rem, 4vw, 3rem)', fontFamily: 'Playfair Display, serif', fontWeight: 700, marginBottom: '0.5rem' },
  sub: { color: 'var(--color-paper-300)', opacity: 0.5, fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', maxWidth: '28rem', margin: '0 auto 2rem' },
  glass: { background: 'rgba(218, 165, 32, 0.05)', backdropFilter: 'blur(16px)', border: '1px solid rgba(218, 165, 32, 0.1)', borderRadius: '1rem', padding: 'clamp(1.25rem, 3vw, 2rem)' },
  btn: { background: 'linear-gradient(135deg, #DAA520, #B8860B)', color: '#0D0B09', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', padding: '0.75rem 2rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer' },
  btnOutline: { border: '1px solid var(--color-gold-500)', color: 'var(--color-gold-400)', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', padding: '0.75rem 2rem', borderRadius: '0.5rem', background: 'transparent', cursor: 'pointer', textDecoration: 'none', display: 'inline-flex', alignItems: 'center' as const },
};

export default function Quiz() {
  const [phase, setPhase] = useState<Phase>('categories');
  const [cat, setCat] = useState<QuizCategory | null>(null);
  const [current, setCurrent] = useState(0);
  const [score, setScore] = useState(0);
  const [answered, setAnswered] = useState<number | null>(null);
  const [totalPlayed, setTotalPlayed] = useState(0);

  const shuffled = useMemo(
    () => (cat ? cat.questions.map(shuffle) : []),
    [cat, totalPlayed] // eslint-disable-line
  );

  const q = shuffled[current];

  const selectCategory = useCallback((c: QuizCategory) => {
    setCat(c);
    setCurrent(0);
    setScore(0);
    setAnswered(null);
    setPhase('playing');
    setTotalPlayed(p => p + 1);
  }, []);

  const handleAnswer = useCallback((idx: number) => {
    if (answered !== null || !q) return;
    setAnswered(idx);
    if (idx === q.shuffledCorrectIndex) setScore(s => s + 1);
    setTimeout(() => {
      setAnswered(null);
      if (current + 1 < shuffled.length) setCurrent(c => c + 1);
      else setPhase('result');
    }, 1000);
  }, [answered, q, current, shuffled.length]);

  const discount = cat ? getDiscount(score, cat.questions.length) : null;

  return (
    <section style={css.section} id="quiz">
      <div style={css.container}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <span style={css.label}>Проверьте себя</span>
          <h2 style={css.heading}>Викторина о войне</h2>
          <p style={css.sub}>
            Три категории, десять вопросов, система скидок за результат
          </p>
        </div>

        {/* === CATEGORY SELECT === */}
        {phase === 'categories' && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
            {categories.map(c => (
              <button key={c.id} onClick={() => selectCategory(c)}
                style={{ ...css.glass, cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.2s' }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(218,165,32,0.25)')}
                onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(218,165,32,0.1)')}>
                <div style={{ width: '2.5rem', height: '2.5rem', borderRadius: '0.75rem', background: 'rgba(218,165,32,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.75rem' }}>
                  <svg viewBox="0 0 24 24" style={{ width: '1.25rem', height: '1.25rem', color: 'var(--color-gold-400)' }} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d={c.icon}/>
                  </svg>
                </div>
                <div style={{ color: 'var(--color-paper-50)', fontFamily: 'PT Serif, serif', fontWeight: 700, fontSize: '1rem', marginBottom: '0.25rem' }}>{c.title}</div>
                <div style={{ color: 'var(--color-paper-300)', opacity: 0.5, fontFamily: 'PT Sans, sans-serif', fontSize: '0.75rem' }}>{c.description}</div>
                <div style={{ color: 'var(--color-gold-600)', fontFamily: 'Courier New, monospace', fontSize: '0.625rem', marginTop: '0.5rem' }}>{c.questions.length} вопросов</div>
              </button>
            ))}
          </div>
        )}

        {/* === PLAYING === */}
        {phase === 'playing' && q && (
          <div style={css.glass}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', fontFamily: 'PT Sans, sans-serif' }}>
              <span style={{ color: 'var(--color-paper-300)', opacity: 0.4, fontSize: '0.75rem' }}>
                {cat?.title} — {current + 1}/{shuffled.length}
              </span>
              <span style={{ color: 'var(--color-gold-400)', fontSize: '0.75rem', fontWeight: 700 }}>
                {score} правильных
              </span>
            </div>

            {/* Progress bar */}
            <div style={{ height: '3px', background: 'rgba(218,165,32,0.1)', borderRadius: '2px', marginBottom: '1.5rem', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${((current + 1) / shuffled.length) * 100}%`, background: 'linear-gradient(90deg, var(--color-gold-600), var(--color-gold-400))', borderRadius: '2px', transition: 'width 0.3s ease' }}/>
            </div>

            <h3 style={{ color: 'var(--color-paper-50)', fontFamily: 'PT Serif, serif', fontSize: '1.125rem', marginBottom: '1.25rem', lineHeight: 1.4 }}>
              {q.question}
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              {q.shuffledOptions.map((opt, idx) => {
                const isCorrect = idx === q.shuffledCorrectIndex;
                const isChosen = answered === idx;
                const show = answered !== null;
                let bg = 'rgba(250,243,232,0.05)', border = '1px solid rgba(218,165,32,0.1)';
                if (show && isCorrect) { bg = 'rgba(107,142,35,0.3)'; border = '1px solid rgba(107,142,35,0.5)'; }
                else if (show && isChosen && !isCorrect) { bg = 'rgba(204,17,51,0.2)'; border = '1px solid rgba(204,17,51,0.4)'; }
                return (
                  <button key={idx} onClick={() => handleAnswer(idx)} disabled={show}
                    style={{ background: bg, border, borderRadius: '0.5rem', padding: '0.75rem 1rem', color: 'var(--color-paper-100)', fontFamily: 'PT Sans, sans-serif', fontSize: '0.8125rem', textAlign: 'left', cursor: show ? 'default' : 'pointer', transition: 'all 0.2s', opacity: show && !isCorrect && !isChosen ? 0.4 : 1 }}>
                    {opt}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* === RESULT === */}
        {phase === 'result' && (
          <div style={{ ...css.glass, textAlign: 'center' }}>
            <div style={{ fontSize: '3.5rem', fontWeight: 700, fontFamily: 'Playfair Display, serif', color: 'var(--color-gold-300)', marginBottom: '0.25rem' }}>
              {score}/{shuffled.length}
            </div>
            <p style={{ color: 'var(--color-paper-300)', opacity: 0.6, fontFamily: 'PT Sans, sans-serif', fontSize: '0.875rem', marginBottom: '1.5rem' }}>
              {score >= 9 ? 'Великолепно! Вы отлично знаете историю!' :
               score >= 7 ? 'Отличный результат! Вы хорошо знаете историю.' :
               score >= 5 ? 'Неплохо! Но есть что вспомнить.' :
               'Стоит освежить знания о Великой Отечественной.'}
            </p>

            {/* Discount reward */}
            {discount && (
              <div style={{ background: 'rgba(107,142,35,0.15)', border: '1px solid rgba(107,142,35,0.3)', borderRadius: '0.75rem', padding: '1.25rem', marginBottom: '1.5rem' }}>
                <div style={{ color: 'var(--color-gold-300)', fontFamily: 'PT Sans, sans-serif', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                  {discount.label} Ваша скидка — {discount.discount}%
                </div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(13,11,9,0.5)', borderRadius: '0.5rem', padding: '0.5rem 1rem' }}>
                  <span style={{ fontFamily: 'Courier New, monospace', color: 'var(--color-gold-300)', fontSize: '1.125rem', letterSpacing: '0.1em', fontWeight: 700 }}>
                    {discount.promo}
                  </span>
                  <button onClick={() => navigator.clipboard?.writeText(discount.promo)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-300)', opacity: 0.5, padding: '2px' }}>
                    <svg viewBox="0 0 24 24" style={{ width: '1rem', height: '1rem' }} fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                  </button>
                </div>
                <p style={{ color: 'var(--color-paper-300)', opacity: 0.4, fontFamily: 'PT Sans, sans-serif', fontSize: '0.7rem', marginTop: '0.5rem' }}>
                  Используйте промокод при заказе «Боевой путь»
                </p>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <button onClick={() => setPhase('categories')} style={css.btn}>
                Другая категория
              </button>
              <button onClick={() => cat && selectCategory(cat)} style={css.btnOutline}>
                Пройти ещё раз
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
