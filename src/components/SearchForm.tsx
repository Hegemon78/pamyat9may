/**
 * Free ancestor search form with archive lookup.
 *
 * Phases: idle → searching → results
 * POST /api/search/quick → { total, awards, losses }
 */
import { useState } from "react";

type Phase = "idle" | "searching" | "results";

interface SearchResult {
  total: number;
  awards: number;
  losses: number;
}

const API_URL = (import.meta as any).env?.PUBLIC_BOT_API_URL || "http://localhost:8081";

const css = {
  section: {
    backgroundColor: "var(--color-bg-900)",
    padding: "clamp(3rem, 6vw, 6rem) 0",
  } as const,
  container: { maxWidth: "42rem", margin: "0 auto", padding: "0 1rem" } as const,
  label: {
    color: "var(--color-gold-500)",
    fontFamily: "PT Sans, sans-serif",
    fontSize: "0.75rem",
    fontWeight: 700,
    letterSpacing: "0.2em",
    textTransform: "uppercase" as const,
    display: "block",
    marginBottom: "0.75rem",
  },
  heading: {
    color: "var(--color-paper-50)",
    fontSize: "clamp(1.875rem, 4vw, 3rem)",
    fontFamily: "Playfair Display, serif",
    fontWeight: 700,
    marginBottom: "0.5rem",
  },
  sub: {
    color: "var(--color-paper-300)",
    opacity: 0.5,
    fontFamily: "PT Sans, sans-serif",
    fontSize: "0.875rem",
    maxWidth: "28rem",
    margin: "0 auto 2rem",
  },
  glass: {
    background: "rgba(218, 165, 32, 0.05)",
    backdropFilter: "blur(16px)",
    border: "1px solid rgba(218, 165, 32, 0.1)",
    borderRadius: "1rem",
    padding: "clamp(1.25rem, 3vw, 2rem)",
  },
  fieldWrapper: { marginBottom: "1rem" } as const,
  fieldLabel: {
    color: "var(--color-paper-300)",
    fontFamily: "PT Sans, sans-serif",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    display: "block",
    marginBottom: "0.375rem",
    opacity: 0.7,
  },
  input: {
    width: "100%",
    background: "rgba(250, 243, 232, 0.05)",
    border: "1px solid rgba(218, 165, 32, 0.15)",
    borderRadius: "0.5rem",
    padding: "0.625rem 0.875rem",
    color: "var(--color-paper-50)",
    fontFamily: "PT Sans, sans-serif",
    fontSize: "0.9375rem",
    outline: "none",
    boxSizing: "border-box" as const,
    transition: "border-color 0.2s",
  },
  row: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" } as const,
  btn: {
    background: "linear-gradient(135deg, #DAA520, #B8860B)",
    color: "#0D0B09",
    fontFamily: "PT Sans, sans-serif",
    fontWeight: 700,
    fontSize: "0.9375rem",
    padding: "0.875rem 2rem",
    borderRadius: "0.5rem",
    border: "none",
    cursor: "pointer",
    width: "100%",
    marginTop: "0.5rem",
  },
  btnOutline: {
    border: "1px solid var(--color-gold-500)",
    color: "var(--color-gold-400)",
    fontFamily: "PT Sans, sans-serif",
    fontWeight: 700,
    fontSize: "0.875rem",
    padding: "0.75rem 2rem",
    borderRadius: "0.5rem",
    background: "transparent",
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center" as const,
  },
};

function LoadingDots() {
  return (
    <span style={{ display: "inline-flex", gap: "4px", alignItems: "center", marginLeft: "6px" }}>
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: "5px",
            height: "5px",
            borderRadius: "50%",
            background: "var(--color-gold-400)",
            display: "inline-block",
            animation: "pulse-glow 1.2s ease-in-out infinite",
            animationDelay: `${i * 0.2}s`,
          }}
        />
      ))}
    </span>
  );
}

export default function SearchForm() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [lastName, setLastName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [birthYear, setBirthYear] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lastName.trim()) return;

    setPhase("searching");
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/search/quick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          last_name: lastName.trim(),
          first_name: firstName.trim() || undefined,
          middle_name: middleName.trim() || undefined,
          birth_year: birthYear ? parseInt(birthYear, 10) : undefined,
        }),
      });

      if (!res.ok) throw new Error(`Ошибка сервера: ${res.status}`);
      const data = await res.json();
      setResult(data);
      setPhase("results");
    } catch (err: any) {
      setError(err.message || "Не удалось выполнить поиск. Попробуйте позже.");
      setPhase("idle");
    }
  };

  const handleReset = () => {
    setPhase("idle");
    setResult(null);
    setError(null);
  };

  const handleInputFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "rgba(218, 165, 32, 0.4)";
  };
  const handleInputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "rgba(218, 165, 32, 0.15)";
  };

  return (
    <section style={css.section} id="search">
      <div style={css.container}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <span style={css.label}>Бесплатный поиск</span>
          <h2 style={css.heading}>Найдите своего героя</h2>
          <p style={css.sub}>
            Проверим 47 миллионов архивных записей за секунды
          </p>
        </div>

        {/* === IDLE — Search Form === */}
        {phase === "idle" && (
          <form style={css.glass} onSubmit={handleSubmit} noValidate>
            {error && (
              <div style={{
                background: "rgba(204, 17, 51, 0.1)",
                border: "1px solid rgba(204, 17, 51, 0.3)",
                borderRadius: "0.5rem",
                padding: "0.75rem 1rem",
                color: "var(--color-paper-100)",
                fontFamily: "PT Sans, sans-serif",
                fontSize: "0.8125rem",
                marginBottom: "1rem",
              }}>
                {error}
              </div>
            )}

            {/* Last name — required */}
            <div style={css.fieldWrapper}>
              <label style={css.fieldLabel}>
                Фамилия <span style={{ color: "var(--color-gold-400)" }}>*</span>
              </label>
              <input
                type="text"
                required
                placeholder="Иванов"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                onFocus={handleInputFocus}
                onBlur={handleInputBlur}
                style={css.input}
              />
            </div>

            {/* First + Middle name — optional */}
            <div style={{ ...css.row, marginBottom: "1rem" }}>
              <div>
                <label style={css.fieldLabel}>Имя</label>
                <input
                  type="text"
                  placeholder="Иван"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  onFocus={handleInputFocus}
                  onBlur={handleInputBlur}
                  style={css.input}
                />
              </div>
              <div>
                <label style={css.fieldLabel}>Отчество</label>
                <input
                  type="text"
                  placeholder="Иванович"
                  value={middleName}
                  onChange={(e) => setMiddleName(e.target.value)}
                  onFocus={handleInputFocus}
                  onBlur={handleInputBlur}
                  style={css.input}
                />
              </div>
            </div>

            {/* Birth year */}
            <div style={css.fieldWrapper}>
              <label style={css.fieldLabel}>Год рождения</label>
              <input
                type="number"
                placeholder="1900"
                min={1860}
                max={1935}
                value={birthYear}
                onChange={(e) => setBirthYear(e.target.value)}
                onFocus={handleInputFocus}
                onBlur={handleInputBlur}
                style={css.input}
              />
            </div>

            <button
              type="submit"
              style={css.btn}
              onMouseEnter={(e) => {
                (e.currentTarget.style.opacity = "0.9");
              }}
              onMouseLeave={(e) => {
                (e.currentTarget.style.opacity = "1");
              }}
            >
              Найти в архивах
            </button>
          </form>
        )}

        {/* === SEARCHING === */}
        {phase === "searching" && (
          <div style={{ ...css.glass, textAlign: "center", padding: "3rem 2rem" }}>
            {/* Spinner */}
            <div style={{ position: "relative", width: "3rem", height: "3rem", margin: "0 auto 1.5rem" }}>
              <svg viewBox="0 0 50 50" style={{
                width: "3rem",
                height: "3rem",
                animation: "spin 1s linear infinite",
              }}>
                <circle
                  cx="25" cy="25" r="20"
                  fill="none"
                  stroke="rgba(218, 165, 32, 0.15)"
                  strokeWidth="4"
                />
                <circle
                  cx="25" cy="25" r="20"
                  fill="none"
                  stroke="#DAA520"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeDasharray="80 125"
                  style={{ transformOrigin: "center", animation: "spin 1s linear infinite" }}
                />
              </svg>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>

            <p style={{
              color: "var(--color-paper-50)",
              fontFamily: "PT Serif, serif",
              fontSize: "1.125rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "0.25rem",
            }}>
              Ищем в архивах
              <LoadingDots />
            </p>
            <p style={{
              color: "var(--color-paper-300)",
              opacity: 0.4,
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.8125rem",
              marginTop: "0.5rem",
            }}>
              Проверяем 6 баз данных
            </p>
          </div>
        )}

        {/* === RESULTS === */}
        {phase === "results" && result && (
          <div style={{ ...css.glass, textAlign: "center" }}>
            {/* Big number */}
            <div style={{
              fontSize: "clamp(3rem, 8vw, 5rem)",
              fontWeight: 700,
              fontFamily: "Playfair Display, serif",
              color: "var(--color-gold-400)",
              lineHeight: 1,
              marginBottom: "0.25rem",
            }}>
              {result.total.toLocaleString("ru-RU")}
            </div>
            <p style={{
              color: "var(--color-paper-50)",
              fontFamily: "PT Serif, serif",
              fontSize: "1.125rem",
              marginBottom: "0.75rem",
            }}>
              {result.total === 1 ? "запись найдена" :
               result.total >= 2 && result.total <= 4 ? "записи найдено" :
               "записей найдено"}
            </p>

            {result.total > 0 && (
              <>
                {/* Breakdown */}
                <div style={{
                  display: "flex",
                  gap: "1rem",
                  justifyContent: "center",
                  flexWrap: "wrap",
                  marginBottom: "1.5rem",
                }}>
                  <div style={{
                    background: "rgba(218, 165, 32, 0.08)",
                    border: "1px solid rgba(218, 165, 32, 0.15)",
                    borderRadius: "0.5rem",
                    padding: "0.5rem 1rem",
                    fontFamily: "PT Sans, sans-serif",
                    fontSize: "0.8125rem",
                    color: "var(--color-paper-300)",
                  }}>
                    <span style={{ color: "var(--color-gold-400)", fontWeight: 700 }}>
                      {result.awards.toLocaleString("ru-RU")}
                    </span>{" "}
                    наградных документов
                  </div>
                  <div style={{
                    background: "rgba(218, 165, 32, 0.08)",
                    border: "1px solid rgba(218, 165, 32, 0.15)",
                    borderRadius: "0.5rem",
                    padding: "0.5rem 1rem",
                    fontFamily: "PT Sans, sans-serif",
                    fontSize: "0.8125rem",
                    color: "var(--color-paper-300)",
                  }}>
                    <span style={{ color: "var(--color-gold-400)", fontWeight: 700 }}>
                      {result.losses.toLocaleString("ru-RU")}
                    </span>{" "}
                    донесений о потерях
                  </div>
                </div>

                {/* Success badge */}
                <div style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  background: "rgba(107, 142, 35, 0.15)",
                  border: "1px solid rgba(107, 142, 35, 0.3)",
                  borderRadius: "2rem",
                  padding: "0.375rem 1rem",
                  marginBottom: "1.5rem",
                }}>
                  <svg viewBox="0 0 24 24" style={{ width: "1rem", height: "1rem", color: "#6B8E23", flexShrink: 0 }} fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span style={{
                    color: "#6B8E23",
                    fontFamily: "PT Sans, sans-serif",
                    fontSize: "0.8125rem",
                    fontWeight: 700,
                  }}>
                    Найдены совпадения в архивах
                  </span>
                </div>

                {/* CTA */}
                <div style={{ marginBottom: "1rem" }}>
                  <a
                    href="#pricing"
                    style={{
                      ...css.btn,
                      display: "inline-block",
                      width: "auto",
                      textDecoration: "none",
                      textAlign: "center",
                      padding: "0.875rem 2.5rem",
                    }}
                  >
                    Получить полный отчёт за 1 990 руб.
                  </a>
                </div>
              </>
            )}

            {result.total === 0 && (
              <p style={{
                color: "var(--color-paper-300)",
                opacity: 0.6,
                fontFamily: "PT Sans, sans-serif",
                fontSize: "0.9375rem",
                margin: "0.5rem 0 1.5rem",
              }}>
                Записей не найдено. Попробуйте другое написание.
              </p>
            )}

            <button onClick={handleReset} style={css.btnOutline}>
              Новый поиск
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
