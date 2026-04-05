/**
 * Paid order placement form with YooKassa redirect support.
 *
 * Phases: form → sending → success | redirect
 * POST /api/order/create → { order_id, payment_url? }
 */
import { useState } from "react";

type Phase = "form" | "sending" | "success" | "redirect";
type ProductType = "photo_ai" | "combat_path" | "family_memory";

interface OrderResponse {
  order_id: string;
  payment_url?: string | null;
}

const API_URL = (import.meta as any).env?.PUBLIC_BOT_API_URL || "http://localhost:8081";

const PRODUCTS: Record<ProductType, { label: string; price: string; kopecks: number }> = {
  photo_ai: { label: "AI-реставрация", price: "299₽", kopecks: 29900 },
  combat_path: { label: "Боевой путь", price: "1 990₽", kopecks: 199000 },
  family_memory: { label: "Память семьи", price: "4 990₽", kopecks: 499000 },
};

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

export default function OrderForm() {
  const [phase, setPhase] = useState<Phase>("form");
  const [productType, setProductType] = useState<ProductType>("combat_path");
  const [orderId, setOrderId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Hero fields
  const [lastName, setLastName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [birthYear, setBirthYear] = useState("");

  // Contact fields
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const handleInputFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "rgba(218, 165, 32, 0.4)";
  };
  const handleInputBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.currentTarget.style.borderColor = "rgba(218, 165, 32, 0.15)";
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lastName.trim() || !email.trim()) return;

    setPhase("sending");
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/order/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_type: productType,
          last_name: lastName.trim(),
          first_name: firstName.trim() || undefined,
          middle_name: middleName.trim() || undefined,
          birth_year: birthYear ? parseInt(birthYear, 10) : undefined,
          contact_email: email.trim(),
          contact_phone: phone.trim() || undefined,
          total_price: PRODUCTS[productType].kopecks,
        }),
      });

      if (!res.ok) throw new Error(`Ошибка сервера: ${res.status}`);
      const data: OrderResponse = await res.json();

      setOrderId(data.order_id);

      if (data.payment_url) {
        setPhase("redirect");
        setTimeout(() => {
          window.location.href = data.payment_url!;
        }, 1500);
      } else {
        setPhase("success");
      }
    } catch (err: any) {
      setError(err.message || "Не удалось создать заказ. Попробуйте позже.");
      setPhase("form");
    }
  };

  const product = PRODUCTS[productType];

  return (
    <section style={css.section} id="order-form">
      <div style={css.container}>
        <div style={{ textAlign: "center", marginBottom: "1.5rem" }}>
          <span style={css.label}>Заказать</span>
          <h2 style={css.heading}>Оформление заказа</h2>
        </div>

        {/* === FORM === */}
        {phase === "form" && (
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

            {/* Product type selector */}
            <div style={{ marginBottom: "1.5rem" }}>
              <label style={css.fieldLabel}>Тип услуги</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.5rem" }}>
                {(Object.entries(PRODUCTS) as [ProductType, typeof PRODUCTS[ProductType]][]).map(
                  ([key, p]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setProductType(key)}
                      style={{
                        padding: "0.625rem 0.5rem",
                        borderRadius: "0.5rem",
                        fontFamily: "PT Sans, sans-serif",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        cursor: "pointer",
                        transition: "all 0.2s",
                        border: productType === key
                          ? "1px solid rgba(218, 165, 32, 0.5)"
                          : "1px solid rgba(218, 165, 32, 0.12)",
                        background: productType === key
                          ? "rgba(218, 165, 32, 0.12)"
                          : "rgba(250, 243, 232, 0.03)",
                        color: productType === key
                          ? "var(--color-gold-400)"
                          : "var(--color-paper-300)",
                        textAlign: "center" as const,
                      }}
                    >
                      <div>{p.label}</div>
                      <div style={{
                        fontSize: "0.6875rem",
                        opacity: 0.7,
                        marginTop: "2px",
                        fontWeight: 400,
                      }}>
                        {p.price}
                      </div>
                    </button>
                  )
                )}
              </div>
            </div>

            {/* Divider */}
            <div style={{ height: "1px", background: "rgba(218, 165, 32, 0.08)", marginBottom: "1.25rem" }} />

            {/* Hero fields */}
            <p style={{
              color: "var(--color-gold-500)",
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.6875rem",
              fontWeight: 700,
              letterSpacing: "0.15em",
              textTransform: "uppercase" as const,
              marginBottom: "0.75rem",
              opacity: 0.8,
            }}>
              Данные героя
            </p>

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

            <div style={{ ...css.fieldWrapper, marginBottom: "1.25rem" }}>
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

            {/* Divider */}
            <div style={{ height: "1px", background: "rgba(218, 165, 32, 0.08)", marginBottom: "1.25rem" }} />

            {/* Contact fields */}
            <p style={{
              color: "var(--color-gold-500)",
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.6875rem",
              fontWeight: 700,
              letterSpacing: "0.15em",
              textTransform: "uppercase" as const,
              marginBottom: "0.75rem",
              opacity: 0.8,
            }}>
              Контакты
            </p>

            <div style={css.fieldWrapper}>
              <label style={css.fieldLabel}>
                Email <span style={{ color: "var(--color-gold-400)" }}>*</span>
              </label>
              <input
                type="email"
                required
                placeholder="ivan@mail.ru"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={handleInputFocus}
                onBlur={handleInputBlur}
                style={css.input}
              />
            </div>

            <div style={css.fieldWrapper}>
              <label style={css.fieldLabel}>Телефон</label>
              <input
                type="tel"
                placeholder="+7 900 000-00-00"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                onFocus={handleInputFocus}
                onBlur={handleInputBlur}
                style={css.input}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              style={css.btn}
              onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.9")}
              onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
            >
              Оформить заказ — {product.price}
            </button>

            <p style={{
              color: "var(--color-paper-300)",
              opacity: 0.35,
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.75rem",
              textAlign: "center" as const,
              marginTop: "0.875rem",
            }}>
              Оплата через ЮKassa. Результат в течение 24 часов.
            </p>
          </form>
        )}

        {/* === SENDING === */}
        {phase === "sending" && (
          <div style={{ ...css.glass, textAlign: "center", padding: "3rem 2rem" }}>
            <div style={{ position: "relative", width: "3rem", height: "3rem", margin: "0 auto 1.5rem" }}>
              <svg viewBox="0 0 50 50" style={{ width: "3rem", height: "3rem", animation: "spin 1s linear infinite" }}>
                <circle cx="25" cy="25" r="20" fill="none" stroke="rgba(218, 165, 32, 0.15)" strokeWidth="4" />
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
            }}>
              Создаём заказ
              <LoadingDots />
            </p>
          </div>
        )}

        {/* === SUCCESS (no payment URL) === */}
        {phase === "success" && (
          <div style={{ ...css.glass, textAlign: "center", padding: "2.5rem 2rem" }}>
            {/* Checkmark */}
            <div style={{
              width: "4rem",
              height: "4rem",
              borderRadius: "50%",
              background: "rgba(107, 142, 35, 0.15)",
              border: "1px solid rgba(107, 142, 35, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 1.5rem",
            }}>
              <svg viewBox="0 0 24 24" style={{ width: "2rem", height: "2rem", color: "#6B8E23" }} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>

            <h3 style={{
              color: "var(--color-paper-50)",
              fontFamily: "Playfair Display, serif",
              fontSize: "1.5rem",
              fontWeight: 700,
              marginBottom: "0.5rem",
            }}>
              Заказ принят!
            </h3>

            {orderId && (
              <p style={{
                color: "var(--color-gold-400)",
                fontFamily: "Courier New, monospace",
                fontSize: "0.875rem",
                letterSpacing: "0.05em",
                marginBottom: "0.75rem",
              }}>
                Номер: {orderId}
              </p>
            )}

            <p style={{
              color: "var(--color-paper-300)",
              opacity: 0.6,
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.9375rem",
            }}>
              Мы свяжемся с вами по email
            </p>
          </div>
        )}

        {/* === REDIRECT (payment_url present) === */}
        {phase === "redirect" && (
          <div style={{ ...css.glass, textAlign: "center", padding: "3rem 2rem" }}>
            {/* Spinner */}
            <div style={{ position: "relative", width: "3rem", height: "3rem", margin: "0 auto 1.5rem" }}>
              <svg viewBox="0 0 50 50" style={{ width: "3rem", height: "3rem", animation: "spin 1s linear infinite" }}>
                <circle cx="25" cy="25" r="20" fill="none" stroke="rgba(218, 165, 32, 0.15)" strokeWidth="4" />
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
            </div>

            <p style={{
              color: "var(--color-paper-50)",
              fontFamily: "PT Serif, serif",
              fontSize: "1.125rem",
              marginBottom: "0.5rem",
            }}>
              Перенаправляем на оплату...
            </p>
            <p style={{
              color: "var(--color-paper-300)",
              opacity: 0.4,
              fontFamily: "PT Sans, sans-serif",
              fontSize: "0.8125rem",
            }}>
              Если не перешли автоматически — обновите страницу
            </p>
          </div>
        )}

      </div>
    </section>
  );
}
