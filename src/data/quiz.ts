export interface QuizQuestion {
  question: string;
  options: string[];
  correctIndex: number;
}

export interface QuizCategory {
  id: string;
  title: string;
  description: string;
  icon: string;
  questions: QuizQuestion[];
}

export const categories: QuizCategory[] = [
  {
    id: 'dates',
    title: 'Даты и события',
    description: 'Ключевые даты Великой Отечественной',
    icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z',
    questions: [
      { question: 'Когда началась Великая Отечественная война?', options: ['22 июня 1941', '1 сентября 1939', '22 июня 1940', '9 мая 1941'], correctIndex: 0 },
      { question: 'Сколько дней длилась блокада Ленинграда?', options: ['672 дня', '872 дня', '1000 дней', '540 дней'], correctIndex: 1 },
      { question: 'Когда Знамя Победы водружено над Рейхстагом?', options: ['9 мая 1945', '2 мая 1945', '30 апреля 1945', '8 мая 1945'], correctIndex: 2 },
      { question: 'Сколько дней длилась Великая Отечественная война?', options: ['1200 дней', '1418 дней', '1500 дней', '1350 дней'], correctIndex: 1 },
      { question: 'Когда состоялся Парад Победы на Красной площади?', options: ['9 мая 1945', '24 июня 1945', '2 мая 1945', '7 ноября 1945'], correctIndex: 1 },
      { question: 'Когда началась Сталинградская битва?', options: ['Июнь 1941', 'Январь 1942', 'Июль 1942', 'Сентябрь 1942'], correctIndex: 2 },
      { question: 'Дата полного снятия блокады Ленинграда?', options: ['27 января 1944', '9 мая 1944', '18 января 1943', '8 сентября 1941'], correctIndex: 0 },
      { question: 'Когда началась Курская битва?', options: ['Февраль 1943', '5 июля 1943', 'Август 1943', 'Январь 1943'], correctIndex: 1 },
      { question: 'Когда началась операция «Багратион»?', options: ['Январь 1944', 'Июнь 1944', 'Март 1944', 'Август 1944'], correctIndex: 1 },
      { question: 'Дата капитуляции Японии (окончание Второй мировой)?', options: ['9 мая 1945', '6 августа 1945', '2 сентября 1945', '15 августа 1945'], correctIndex: 2 },
    ],
  },
  {
    id: 'heroes',
    title: 'Герои и командиры',
    description: 'Люди, приблизившие Победу',
    icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    questions: [
      { question: 'Кто командовал парадом Победы 24 июня 1945?', options: ['Жуков', 'Рокоссовский', 'Конев', 'Василевский'], correctIndex: 1 },
      { question: 'Маршал, принимавший капитуляцию Германии?', options: ['Рокоссовский', 'Конев', 'Жуков', 'Тимошенко'], correctIndex: 2 },
      { question: 'Кто автор слов песни «Священная война»?', options: ['Лебедев-Кумач', 'Симонов', 'Исаковский', 'Твардовский'], correctIndex: 0 },
      { question: 'Лётчик, совершивший первый ночной таран?', options: ['Покрышкин', 'Талалихин', 'Кожедуб', 'Гастелло'], correctIndex: 1 },
      { question: 'Кто написал стихотворение «Жди меня»?', options: ['Твардовский', 'Симонов', 'Сурков', 'Исаковский'], correctIndex: 1 },
      { question: 'Снайпер, уничтоживший 225 солдат противника в Сталинграде?', options: ['Морозов', 'Зайцев', 'Павличенко', 'Номоконов'], correctIndex: 1 },
      { question: 'Кто командовал обороной Сталинграда?', options: ['Жуков', 'Чуйков', 'Рокоссовский', 'Ватутин'], correctIndex: 1 },
      { question: 'Легендарная женщина-снайпер с 309 подтверждёнными?', options: ['Павличенко', 'Шанина', 'Космодемьянская', 'Гризодубова'], correctIndex: 0 },
      { question: 'Кто водрузил Знамя Победы над Рейхстагом?', options: ['Жуков и Конев', 'Егоров и Кантария', 'Берест и Неустроев', 'Казаков и Сорокин'], correctIndex: 1 },
      { question: 'Трижды Герой Советского Союза, лётчик-ас?', options: ['Покрышкин', 'Кожедуб', 'Гастелло', 'Талалихин'], correctIndex: 1 },
    ],
  },
  {
    id: 'battles',
    title: 'Битвы и техника',
    description: 'Сражения, оружие, стратегия',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    questions: [
      { question: 'Крупнейшее танковое сражение в истории?', options: ['Сталинградская битва', 'Битва за Москву', 'Курская битва', 'Битва за Берлин'], correctIndex: 2 },
      { question: 'Какой город-герой стоит на Волге?', options: ['Ленинград', 'Москва', 'Сталинград', 'Минск'], correctIndex: 2 },
      { question: 'Что освободила операция «Багратион»?', options: ['Украину', 'Белоруссию', 'Прибалтику', 'Польшу'], correctIndex: 1 },
      { question: 'Название легендарного советского танка?', options: ['КВ-1', 'Т-34', 'ИС-2', 'БТ-7'], correctIndex: 1 },
      { question: 'Какой самолёт называли «ночной ведьмой»?', options: ['Ил-2', 'По-2', 'Як-1', 'Ла-5'], correctIndex: 1 },
      { question: 'Где произошла Прохоровская танковая битва?', options: ['Под Москвой', 'Под Курском', 'Под Сталинградом', 'Под Ленинградом'], correctIndex: 1 },
      { question: 'Как называлась «Дорога жизни»?', options: ['Путь через Волгу', 'Переправа через Днепр', 'Путь по Ладожскому озеру', 'Дорога через Урал'], correctIndex: 2 },
      { question: 'Название реактивной установки, прозванной «Катюша»?', options: ['БМ-8', 'БМ-13', 'БМ-21', 'БМ-31'], correctIndex: 1 },
      { question: 'Сколько городов получили звание «Город-герой»?', options: ['9', '12', '13', '15'], correctIndex: 2 },
      { question: 'Штурмовик Ил-2 называли...', options: ['Летающий танк', 'Чёрная смерть', 'Оба названия верны', 'Красная звезда'], correctIndex: 2 },
    ],
  },
];

// Flat export for backward compatibility
export const questions = categories[0].questions;

// Discount tiers based on score
export const discountTiers = [
  { minScore: 10, discount: 30, promo: 'POBEDA30', label: 'Отличник!' },
  { minScore: 8, discount: 20, promo: 'GEROI20', label: 'Хорошо!' },
  { minScore: 6, discount: 10, promo: 'PAMYAT10', label: 'Неплохо!' },
] as const;

export function getDiscount(score: number, total: number) {
  const pct = score / total;
  if (pct >= 1) return discountTiers[0];
  if (pct >= 0.8) return discountTiers[1];
  if (pct >= 0.6) return discountTiers[2];
  return null;
}
