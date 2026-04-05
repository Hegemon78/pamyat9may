# TODO Frontend — Задачи для фронтенд-разработчика

> Проект "Память 9 Мая" — MVP готов на ~80%. Нужен финальный визуальный полиш.
> Стек: Astro 5, React 19, Tailwind CSS 4. Тёмная тема, золотые акценты.

---

## Приоритет 1 — Критичное (до запуска)

### 1.1 Mobile-first Responsive
- [ ] **Header** (`BaseLayout.astro`): hamburger menu для мобильных (сейчас `hidden md:flex`)
- [ ] **Hero** (`Hero.astro`): проверить размеры шрифтов на 375px, кнопки в колонку на мобильных
- [ ] **Timeline** (`Timeline.astro`): на мобильных карточки все слева — проверить отступы
- [ ] **Quiz** (`Quiz.tsx`): grid 2x2 может ломаться на маленьких экранах — сделать 1 колонку на <400px
- [ ] **BeforeAfterSlider** (`BeforeAfterSlider.astro`): добавить touch gesture support для iOS/Android
- [ ] **MemoryWallPreview**: карточки должны быть в 1 колонку на мобильных

### 1.2 Реальные фотографии
- [ ] **BeforeAfterSlider**: заменить SVG-плейсхолдеры на реальные фото (до/после AI-обработки)
- [ ] **MemoryWallPreview**: добавить фото-миниатюры к карточкам историй
- [ ] **Hero**: фоновое фото или видео вместо чистого градиента
- [ ] **OG-изображение**: создать og-image.jpg (1200x630) для социальных сетей

### 1.3 Анимации
- [ ] **FAQ** (`FAQ.astro`): плавная анимация высоты при открытии/закрытии (сейчас мгновенно)
- [ ] **Quiz** (`Quiz.tsx`): зелёная вспышка при правильном ответе, красная тряска при неправильном
- [ ] **Timeline**: параллакс-эффект на линии таймлайна при скролле
- [ ] **Scroll indicator** в Hero: улучшить анимацию (bounce + fade)

---

## Приоритет 2 — Улучшения UX

### 2.1 Визуальные доработки
- [ ] **Glassmorphism карточки**: проверить на Safari (webkit-backdrop-filter может не работать)
- [ ] **Gradient text** (.text-gold-gradient): проверить на всех браузерах
- [ ] **Particles** в Hero: добавить больше частиц (сейчас только 2 через CSS ::before/::after)
- [ ] **Eternal flame SVG**: улучшить анимацию пламени (flicker более реалистичный)
- [ ] **George ribbon stripe**: проверить цвета и ширину полос

### 2.2 Навигация
- [ ] **Smooth scroll**: для якорных ссылок (#revive, #quiz, #timeline, #faq)
- [ ] **Active section highlight**: подсветка текущей секции в навигации при скролле
- [ ] **Back to top button**: появляется после скролла вниз
- [ ] **Mobile menu**: slide-in панель с анимацией

### 2.3 Стена памяти (wall.astro)
- [ ] **Infinite scroll / Load more**: пагинация при большом количестве историй
- [ ] **Masonry layout**: разная высота карточек вместо строгой сетки
- [ ] **Поиск**: фильтрация историй по имени героя
- [ ] **Share**: кнопка "Поделиться историей" на каждой карточке

---

## Приоритет 3 — Дополнительные фичи

### 3.1 Производительность
- [ ] **Lazy loading**: изображения и тяжёлые секции
- [ ] **WebP**: все изображения в современных форматах
- [ ] **Critical CSS**: inline critical styles для первого экрана
- [ ] **Lighthouse**: довести все метрики до >90

### 3.2 SEO & Accessibility
- [ ] **Schema.org**: разметка Event + Organization
- [ ] **Alt-тексты**: для всех изображений и SVG
- [ ] **ARIA labels**: для интерактивных элементов (слайдер, аккордеон, викторина)
- [ ] **Focus trap**: в модальных окнах и викторине
- [ ] **Skip navigation**: для keyboard users
- [ ] **prefers-reduced-motion**: проверить что все анимации отключаются

### 3.3 Социальные фичи
- [ ] **Share results**: кнопка "Поделиться результатом викторины" в соцсетях
- [ ] **Leaderboard**: таблица лидеров викторины (данные из бот API)
- [ ] **Story submission from site**: форма отправки истории прямо с сайта (POST /api/stories)

---

## CSS-переменные (для кастомизации темы)

Все цвета определены через CSS-переменные в `src/styles/global.css`:

```css
--color-bg-900: #0D0B09;     /* Основной фон */
--color-bg-800: #141210;     /* Секции */
--color-gold-500: #d4a544;   /* Основной акцент */
--color-gold-400: #DAA520;   /* Вторичный акцент */
--color-paper-50: #FAF3E8;   /* Основной текст */
--color-paper-300: #DCC9A3;  /* Вторичный текст */
--color-red-400: #DC143C;    /* Советский красный */
--color-george: #E87B2F;     /* Георгиевская лента */
```

Для смены палитры достаточно изменить значения в `@theme { }`.

---

## Структура файлов

```
src/
├── components/
│   ├── Hero.astro              — Hero: пламя, обратный отсчёт, счётчики, паттерн
│   ├── BeforeAfterSlider.astro — Слайдер до/после (SVG → нужны фото!)
│   ├── HowItWorks.astro        — 3 шага (нужны SVG-иллюстрации)
│   ├── HeroStories.astro       — Истории героев с цитатами и наградами
│   ├── Timeline.astro          — Хронология войны (9 событий)
│   ├── MemoryWallPreview.astro — Превью стены памяти
│   ├── FAQ.astro               — Аккордеон FAQ (6 вопросов)
│   ├── CTABanner.astro         — Финальный CTA
│   └── Quiz.tsx                — 3 категории, 30 вопросов, скидки (React)
├── layouts/
│   └── BaseLayout.astro        — Layout + header + footer
├── pages/
│   ├── index.astro             — Главная (все секции)
│   └── wall.astro              — Стена памяти
├── styles/
│   └── global.css              — Tailwind + тема + анимации
└── data/
    ├── timeline.ts             — Данные хронологии
    └── quiz.ts                 — Вопросы викторины
```

---

## Как запустить

```bash
cd app/
npm install
npm run dev      # localhost:4321
```

Бот (отдельно):
```bash
cd bot/
pip install -r requirements.txt
cp .env.example .env  # вписать BOT_TOKEN
python bot.py
```
