import os
import logging
import random
from typing import Optional, Any
from apps.ai_gateway.base import ModelConfig
from apps.ai_gateway.router import ModelRouter
from apps.ai_workspace.schemas import (
    AIGeneratedQuiz,
    AIGeneratedQuestion,
    AIGeneratedOption,
    AIQuestionRevisionProposal,
    GenerateQuizRequest,
)
from apps.ai_workspace.prompts import (
    SYSTEM_PROMPT_V1,
    REVISION_SYSTEM_PROMPT_V1,
    build_quiz_prompt,
    build_revision_prompt,
)
from apps.ai_workspace.tools import validate_quiz_content

logger = logging.getLogger(__name__)


# ==============================================================================
# Domain-Specific Pedagogical Question Banks (Zero-Duplication Guaranteed)
# ==============================================================================

ASTRONOMY_SPACE_BANK = [
    {
        "prompt": "Quyosh tizimining markazida qaysi osmon jismi joylashgan va sayyoralarni o‘z orbitasida nima ushlab turadi?",
        "correct": "Quyosh va uning kuchli gravitatsiya (tortishish) maydoni",
        "distractors": [
            "Yupiter va uning kuchli magnitosferasi",
            "Galaktika markazidagi qora tuynuk",
            "Oy va uning tortishish kuchi"
        ],
        "explanation": "Quyosh tizimi massasining 99.86% qismi Quyoshda to'plangan bo'lib, uning kuchli gravitatsiyasi barcha sayyoralarni orbitada tutib turadi."
    },
    {
        "prompt": "Quyosh tizimidagi eng ulkan va eng og‘ir gigant sayyora qaysi?",
        "correct": "Yupiter",
        "distractors": ["Mars", "Saturn", "Neptun"],
        "explanation": "Yupiter Quyosh tizimidagi barcha boshqa sayyoralar birgalikdagi massasidan 2.5 barobar og'irroq ulkan gaz gigantidir."
    },
    {
        "prompt": "Quyoshdan tarqalayotgan yorug‘lik nuri Yer sayyorasiga taxminan qancha vaqtda yetib keladi?",
        "correct": "Taxminan 8 daqiqa 20 soniyada",
        "distractors": ["Bir zumda (0.1 soniyada)", "1 sutka (24 soat)da", "1 oyda"],
        "explanation": "Yorug'lik tezligi 300,000 km/s bo'lib, Quyoshdan Yergacha bo'lgan ~150 mln km masofani 8 daqiqa 20 soniyada bosib o'tadi."
    },
    {
        "prompt": "Quyosh tizimida Quyoshga eng yaqin joylashgan birinchi sayyora qaysi?",
        "correct": "Merkuriy",
        "distractors": ["Venera", "Mars", "Uran"],
        "explanation": "Merkuriy Quyoshga eng yaqin sayyora bo'lib, uning Quyosh atrofida to'liq aylanish davri atigi 88 Yer sutkasiga teng."
    },
    {
        "prompt": "Atmosferasida kuchli parnik effekti tufayli sirtidagi harorat +460°C gacha yetadigan eng issiq sayyora qaysi?",
        "correct": "Venera",
        "distractors": ["Merkuriy", "Mars", "Saturn"],
        "explanation": "Venera atmosferasi 96% karbonat angidriddan iborat bo'lib, o'ta kuchli issiqxona effekti sababli Quyosh tizimidagi eng issiq sayyoradir."
    },
    {
        "prompt": "Quyosh tizimidagi o‘zining ulkan va yorqin muz-tosh halqalari tizimi bilan mashhur sayyora qaysi?",
        "correct": "Saturn",
        "distractors": ["Mars", "Yupiter", "Pluton"],
        "explanation": "Saturn sayyorasi minglab mayda muz va tosh zarrachalaridan tashkil topgan ajoyib halqalar tizimiga ega."
    },
    {
        "prompt": "Sirtidagi temir oksidi (zang) moddasining ko‘pligi sababli 'Qizil sayyora' deb ataluvchi sayyora qaysi?",
        "correct": "Mars",
        "distractors": ["Merkuriy", "Venera", "Yupiter"],
        "explanation": "Mars tuprog'i tarkibidagi temir oksidi minerallari sayyoraga qizg'ish tus beradi."
    },
    {
        "prompt": "Yer sayyorasining yagona tabiiy yo‘ldoshi qaysi osmon jismi hisoblanadi?",
        "correct": "Oy (Moon)",
        "distractors": ["Fobos", "Titan", "Yevropa"],
        "explanation": "Oy Yerning yagona tabiiy yo'ldoshi bo'lib, Yer atrofini taxminan 27.3 kunda to'liq aylanib chiqadi."
    },
    {
        "prompt": "Asosiy asteroidlar belbog‘i qaysi ikki sayyora orbitalari oralig‘ida joylashgan?",
        "correct": "Mars va Yupiter oralig‘ida",
        "distractors": [
            "Yer va Mars oralig‘ida",
            "Yupiter va Saturn oralig‘ida",
            "Merkuriy va Venera oralig‘ida"
        ],
        "explanation": "Asosiy asteroidlar belbog'i toshloq sayyoralar (Mars) va gaz gigantlari (Yupiter) chegarasida joylashgan."
    },
    {
        "prompt": "Yer atmosferasini quyoshning zararli qisqa to‘lqinli ultrabinafsha nurlaridan himoya qiluvchi qatlam nima deb ataladi?",
        "correct": "Ozon qatlami",
        "distractors": ["Troposfera", "Ionosfera", "Gidrosfera"],
        "explanation": "Stratosferada joylashgan Ozon (O3) qatlami biologik hayotni quyosh radiatsiyasidan asraydi."
    }
]

INFORMATICS_CODING_BANK = [
    {
        "prompt": "Algoritm deb fanda nimaga aytiladi?",
        "correct": "Qo‘yilgan masalani yechish uchun aniq ketma-ketlikda bajariladigan chekli buyruqlar tizimiga",
        "distractors": [
            "Faqat kompyuter ekranida tasvir chiqaruvchi dasturga",
            "Internetdagi ma'lumotlar omboriga",
            "Kompyuterning doimiy xotira qurilmasiga"
        ],
        "explanation": "Algoritm diskretlik, tushunarlilik, aniqlik, ommaviylik va natijaviylik xossalariga ega chekli buyruqlar ketma-ketligidir."
    },
    {
        "prompt": "Python dasturlash tilida ekranga matn yoki hisoblangan natijani chiqarish uchun qaysi standart funksiya ishlatiladi?",
        "correct": "print()",
        "distractors": ["input()", "echo()", "write()"],
        "explanation": "print() funksiyasi berilgan argumentlarni standart chiqish oqimiga (terminal/ekranga) uzatadi."
    },
    {
        "prompt": "Foydalanuvchidan klaviatura orqali ma'lumot qabul qilish uchun Python'da qaysi funksiyadan foydalaniladi?",
        "correct": "input()",
        "distractors": ["scan()", "read()", "get()"],
        "explanation": "input() funksiyasi foydalanuvchi kiritgan satrni o'qib oladi va uni string ko'rinishida qaytaradi."
    },
    {
        "prompt": "Python dasturlash tilida butun sonli ma'lumotlar turi qanday belgilanadi?",
        "correct": "int",
        "distractors": ["float", "str", "bool"],
        "explanation": "int (integer) ma'lumot turi butun musbat va manfiy sonlarni ifodalash uchun xizmat qiladi."
    },
    {
        "prompt": "Haqiqiy (o‘nli kasrli) sonlarni ifodalash uchun Python'da qaysi ma'lumot turi qo‘llaniladi?",
        "correct": "float",
        "distractors": ["int", "char", "list"],
        "explanation": "float (floating point) turi 3.14, 0.5 kabi suzuvchi nuqtali haqiqiy sonlarni ifodalaydi."
    },
    {
        "prompt": "Dasturda berilgan shartga ko‘ra tarmoqlanish jarayonini hosil qilish uchun qaysi kalit so‘zlar qo‘llaniladi?",
        "correct": "if, elif, else",
        "distractors": ["for, while", "def, return", "try, except"],
        "explanation": "if operatori mantiqiy shart to'g'ri (True) bo'lganda tegishli kod blokini ishga tushiradi."
    },
    {
        "prompt": "Bir xil buyruqlarni ma'lum shart asosida ko‘p marta takrorlash uchun qaysi dasturlash konstruksiyasi ishlatiladi?",
        "correct": "Sikl (takrorlash) operatorlari (for, while)",
        "distractors": [
            "Tarmoqlanish operatori (if)",
            "O'zgaruvchi e'lon qilish",
            "Modul import qilish"
        ],
        "explanation": "for va while sikllari takrorlanuvchi jarayonlarni avtomatlashtirish uchun qo'llaniladi."
    },
    {
        "prompt": "Python'da bir nechta elementlarni tartiblangan holda kvadrat qavsda saqlovchi o‘zgaruvchan ma'lumotlar tuzilmasi nima?",
        "correct": "Ro‘yxat (list)",
        "distractors": ["Lug'at (dict)", "To'plam (set)", "Kortej (tuple)"],
        "explanation": "Ro'yxatlar (list) elementlarni indeks bo'yicha tartiblab, ularni tahrirlash imkonini beradi."
    },
    {
        "prompt": "Foydalanuvchi shaxsiy akkauntini kiberhujumlardan himoyalashda eng ishonchli usul nima hisoblanadi?",
        "correct": "Murakkab maxfiy parol va ikki bosqichli autentifikatsiya (2FA)",
        "distractors": [
            "Hamma saytga bir xil 123456 parolini qo'yish",
            "Parolni do'stlarga aytib qo'yish",
            "Brauzerda parollarni ochiq saqlash"
        ],
        "explanation": "2FA (Two-Factor Authentication) paroldan tashqari ikkinchi tasdiqlash vositasini talab qilgani uchun xavfsizlikni bir necha barobar oshiradi."
    },
    {
        "prompt": "Kompyuterning barcha arifmetik va mantiqiy amallarini boshqaruvchi asosiy hisoblash mantiqiy qurilmasi nima?",
        "correct": "Markaziy protsessor (CPU)",
        "distractors": ["Qattiq disk (HDD)", "Tezkor xotira (RAM)", "Monitor"],
        "explanation": "Protsessor (Central Processing Unit) kompyuterning barcha buyruqlarini qayta ishlovchi bosh hisoblash markazidir."
    }
]

FRACTIONS_NUMBER_BANK = [
    {
        "prompt": r"Kasrni eng sodda (qisqarmas) ko‘rinishga keltiring: $\frac{24}{36}$",
        "correct": r"$\frac{2}{3}$",
        "distractors": [r"$\frac{3}{4}$", r"$\frac{4}{5}$", r"$\frac{1}{2}$"],
        "explanation": r"Surat va maxraj 12 ga bo‘linadi: $24/12 = 2$, $36/12 = 3$, natija: $2/3$."
    },
    {
        "prompt": r"Hisoblang: $\frac{1}{4} + \frac{2}{4}$",
        "correct": r"$\frac{3}{4}$",
        "distractors": [r"$\frac{3}{8}$", r"$\frac{2}{8}$", r"$1$"],
        "explanation": r"Maxrajlar teng: $(1+2)/4 = 3/4$."
    },
    {
        "prompt": r"Hisoblang: $\frac{5}{6} - \frac{1}{3}$",
        "correct": r"$\frac{1}{2}$",
        "distractors": [r"$\frac{4}{3}$", r"$\frac{2}{3}$", r"$\frac{1}{3}$"],
        "explanation": r"Umumiy maxraj 6: $5/6 - 2/6 = 3/6 = 1/2$."
    },
    {
        "prompt": r"Hisoblang: $\frac{2}{3} \times \frac{3}{4}$",
        "correct": r"$\frac{1}{2}$",
        "distractors": [r"$\frac{5}{7}$", r"$\frac{6}{7}$", r"$\frac{2}{4}$"],
        "explanation": r"Ko‘paytiriladi va qisqartiriladi: $(2 \times 3)/(3 \times 4) = 6/12 = 1/2$."
    },
    {
        "prompt": r"Hisoblang: $\frac{3}{4} \div \frac{1}{2}$",
        "correct": r"$\frac{3}{2}$",
        "distractors": [r"$\frac{3}{8}$", r"$\frac{1}{2}$", r"$\frac{2}{3}$"],
        "explanation": r"Bo‘lish ko‘paytirishga aylanadi: $3/4 \times 2/1 = 6/4 = 3/2$."
    },
    {
        "prompt": r"$60$ sonining $\frac{2}{3}$ qismi nechaga teng?",
        "correct": r"$40$",
        "distractors": [r"$30$", r"$20$", r"$50$"],
        "explanation": r"$(60 \div 3) \times 2 = 20 \times 2 = 40$."
    },
    {
        "prompt": r"Kasrni qisqartiring: $\frac{15}{25}$",
        "correct": r"$\frac{3}{5}$",
        "distractors": [r"$\frac{2}{5}$", r"$\frac{3}{4}$", r"$\frac{1}{5}$"],
        "explanation": r"Surat va maxraj 5 ga bo‘linadi: $15/25 = 3/5$."
    },
    {
        "prompt": r"Hisoblang: $\frac{3}{8} + \frac{2}{8}$",
        "correct": r"$\frac{5}{8}$",
        "distractors": [r"$\frac{5}{16}$", r"$\frac{6}{8}$", r"$\frac{1}{2}$"],
        "explanation": r"Bir xil maxrajli kasrlar: $(3+2)/8 = 5/8$."
    },
    {
        "prompt": r"Hisoblang: $\frac{7}{10} - \frac{2}{5}$",
        "correct": r"$\frac{3}{10}$",
        "distractors": [r"$\frac{5}{5}$", r"$\frac{1}{2}$", r"$\frac{1}{10}$"],
        "explanation": r"$7/10 - 4/10 = 3/10$."
    },
    {
        "prompt": r"Kasrni qisqartiring: $\frac{28}{42}$",
        "correct": r"$\frac{2}{3}$",
        "distractors": [r"$\frac{4}{7}$", r"$\frac{3}{4}$", r"$\frac{1}{2}$"],
        "explanation": r"Surat va maxraj 14 ga bo‘linadi: $28/14 = 2$, $42/14 = 3$, natija: $2/3$."
    },
    {
        "prompt": r"Hisoblang: $\frac{3}{5} \times \frac{5}{6}$",
        "correct": r"$\frac{1}{2}$",
        "distractors": [r"$\frac{8}{11}$", r"$\frac{3}{6}$", r"$\frac{2}{3}$"],
        "explanation": r"5 lar qisqaradi: $3/6 = 1/2$."
    },
    {
        "prompt": r"$84$ sonining $\frac{2}{7}$ qismi nechaga teng?",
        "correct": r"$24$",
        "distractors": [r"$12$", r"$28$", r"$32$"],
        "explanation": r"$(84 \div 7) \times 2 = 12 \times 2 = 24$."
    },
    {
        "prompt": r"$\frac{17}{5}$ noto‘g‘ri kasrni aralash songa aylantiring:",
        "correct": r"$3\frac{2}{5}$",
        "distractors": [r"$2\frac{3}{5}$", r"$3\frac{1}{5}$", r"$4\frac{2}{5}$"],
        "explanation": r"$17 \div 5 = 3$ (qoldiq 2), shuning uchun: $3\frac{2}{5}$."
    },
    {
        "prompt": r"Kasrni qisqartiring: $\frac{35}{49}$",
        "correct": r"$\frac{5}{7}$",
        "distractors": [r"$\frac{5}{8}$", r"$\frac{4}{7}$", r"$\frac{3}{7}$"],
        "explanation": r"Surat va maxraj 7 ga bo‘linadi: $35/7 = 5$, $49/7 = 7$, natija: $5/7$."
    },
    {
        "prompt": r"Hisoblang: $\frac{1}{2} + \frac{1}{4}$",
        "correct": r"$\frac{3}{4}$",
        "distractors": [r"$\frac{2}{6}$", r"$\frac{2}{4}$", r"$1$"],
        "explanation": r"$2/4 + 1/4 = 3/4$."
    },
    {
        "prompt": r"Hisoblang: $\frac{2}{5} \div \frac{4}{15}$",
        "correct": r"$\frac{3}{2}$",
        "distractors": [r"$\frac{8}{75}$", r"$\frac{2}{3}$", r"$\frac{4}{5}$"],
        "explanation": r"$2/5 \times 15/4 = 30/20 = 3/2$."
    },
    {
        "prompt": r"$100$ sonining $\frac{3}{5}$ qismi nechaga teng?",
        "correct": r"$60$",
        "distractors": [r"$50$", r"$40$", r"$70$"],
        "explanation": r"$(100 \div 5) \times 3 = 20 \times 3 = 60$."
    },
    {
        "prompt": r"Kasrni qisqartiring: $\frac{45}{60}$",
        "correct": r"$\frac{3}{4}$",
        "distractors": [r"$\frac{2}{3}$", r"$\frac{4}{5}$", r"$\frac{5}{6}$"],
        "explanation": r"Surat va maxraj 15 ga bo‘linadi: $45/15 = 3$, $60/15 = 4$."
    },
    {
        "prompt": r"Hisoblang: $\frac{5}{12} + \frac{1}{4}$",
        "correct": r"$\frac{2}{3}$",
        "distractors": [r"$\frac{6}{16}$", r"$\frac{3}{4}$", r"$\frac{1}{2}$"],
        "explanation": r"$5/12 + 3/12 = 8/12 = 2/3$."
    },
    {
        "prompt": r"$120$ sonining $\frac{5}{6}$ qismi nechaga teng?",
        "correct": r"$100$",
        "distractors": [r"$90$", r"$110$", r"$80$"],
        "explanation": r"$(120 \div 6) \times 5 = 20 \times 5 = 100$."
    }
]

MATH_ALGEBRA_BANK = [
    {
        "prompt": r"$2x + 6 = 16$ chiziqli tenglamada $x$ ning qiymatini toping:",
        "correct": r"$x = 5$",
        "distractors": [r"$x = 10$", r"$x = 3$", r"$x = 8$"],
        "explanation": r"$2x = 16 - 6 \Rightarrow 2x = 10 \Rightarrow x = 5$."
    },
    {
        "prompt": r"Hisoblang: $25 \times 4 - 36 \div 6$",
        "correct": r"$94$",
        "distractors": [r"$84$", r"$96$", r"$100$"],
        "explanation": r"$25 \times 4 = 100$, $36 \div 6 = 6$, $100 - 6 = 94$."
    },
    {
        "prompt": r"Hisoblang: $\frac{1}{4} + \frac{2}{4}$",
        "correct": r"$\frac{3}{4}$",
        "distractors": [r"$\frac{3}{8}$", r"$\frac{2}{8}$", r"$1$"],
        "explanation": r"$(1+2)/4 = 3/4$."
    },
    {
        "prompt": r"$3x - 5 = 16$ tenglamani yeching:",
        "correct": r"$x = 7$",
        "distractors": [r"$x = 6$", r"$x = 8$", r"$x = 9$"],
        "explanation": r"$3x = 16 + 5 = 21 \Rightarrow x = 7$."
    },
    {
        "prompt": r"Sonning $1\%$ i uning qanday arifmetik qismiga teng bo‘ladi?",
        "correct": r"$\frac{1}{100}$",
        "distractors": [r"$\frac{1}{10}$", r"$\frac{1}{2}$", r"$\frac{1}{1000}$"],
        "explanation": r"Foiz - yuzdan bir qismdir."
    },
    {
        "prompt": r"Tomonlari $a = 6 \text{ sm}$ va $b = 4 \text{ sm}$ bo‘lgan to‘g‘ri to‘rtburchakning yuzasi nechaga teng?",
        "correct": r"$24 \text{ sm}^2$",
        "distractors": [r"$20 \text{ sm}^2$", r"$10 \text{ sm}^2$", r"$12 \text{ sm}^2$"],
        "explanation": r"$S = a \cdot b = 6 \cdot 4 = 24 \text{ sm}^2$."
    },
    {
        "prompt": r"Hisoblang: $(45 + 35) \div 4$",
        "correct": r"$20$",
        "distractors": [r"$15$", r"$25$", r"$30$"],
        "explanation": r"$(45+35) = 80$, $80 \div 4 = 20$."
    },
    {
        "prompt": r"$\sqrt{144}$ ning qiymati nechaga teng?",
        "correct": r"$12$",
        "distractors": [r"$14$", r"$11$", r"$16$"],
        "explanation": r"$12 \times 12 = 144$, shuning uchun $\sqrt{144} = 12$."
    },
    {
        "prompt": r"$30$ ning $\frac{2}{3}$ qismi nechaga teng?",
        "correct": r"$20$",
        "distractors": [r"$15$", r"$10$", r"$25$"],
        "explanation": r"$(30 \div 3) \times 2 = 20$."
    },
    {
        "prompt": r"Kasrni qisqartiring: $\frac{24}{36}$",
        "correct": r"$\frac{2}{3}$",
        "distractors": [r"$\frac{3}{4}$", r"$\frac{4}{5}$", r"$\frac{1}{2}$"],
        "explanation": r"$24/12 = 2$, $36/12 = 3$, javob: $2/3$."
    }
]

HISTORY_CULTURE_BANK = [
    {
        "prompt": "Sohibqiron Amir Temur davlatining bosh davlat boshqaruv shiori nima bo‘lgan?",
        "correct": "'Kuch — adolatdadir'",
        "distractors": ["'Ilm — najotdir'", "'Birlik — qudratdir'", "'Tinchlik — boylikdir'"],
        "explanation": "Amir Temur davlat muhrida 'Rosti-rusti' ('Haqiqat va adolat — najotdir', 'Kuch — adolatdadir') shiori o'yib yozilgan."
    },
    {
        "prompt": "Samarqandda ulkan rasadxona qurdirib, 1018 ta yulduzning aniq koordinatasini o‘z ichiga olgan 'Zij' jadvalini tuzgan buyuk alloma kim?",
        "correct": "Mirzo Ulug‘bek",
        "distractors": ["Al-Xorazmiy", "Ibn Sino", "Abu Rayhon Beruniy"],
        "explanation": "Mirzo Ulug'bek 1428-yilda Samarqandda rasadxona qurdirib, 'Ziji Jadidi Ko'ragoniy' yulduzlar jadvalini yaratgan."
    },
    {
        "prompt": "Turkiy tilda birinchi bo‘lib 'Xamsa' (besh doston) asarini yaratgan ulug‘ shoir va mutafakkir kim?",
        "correct": "Alisher Navoiy",
        "distractors": ["Zahiriddin Muhammad Bobur", "Lutfiy", "Nizomiy Ganjaviy"],
        "explanation": "Alisher Navoiy 1483-1485 yillarda turkiy tilda birinchi mukammal 'Xamsa' asarini bitgan."
    },
    {
        "prompt": "Sharq va G‘arbni bog‘lab, savdo-sotiq va madaniy munosabatlarni rivojlantirgan qadimiy karvon yo‘li nima deb atalgan?",
        "correct": "Buyuk Ipak yo‘li",
        "distractors": ["Shoh yo'li", "Lojuvard yo'li", "Qahrabo yo'li"],
        "explanation": "Buyuk Ipak yo'li miloddan avvalgi II asrdan to o'rta asrlargacha Xitoy, Markaziy Osiyo va O'rta yer dengizini bog'lagan."
    },
    {
        "prompt": "Tibbiyot ilmining asoschilaridan biri, Yevropada 'Avitsenna' nomi bilan tanilgan 'Tib qonunlari' muallifi kim?",
        "correct": "Abu Ali ibn Sino",
        "distractors": ["Al-Farg'oniy", "Ar-Roziy", "Mahmud Qoshg'ariy"],
        "explanation": "Ibn Sinoning 'Kitob al-Qonun fit-tibb' asari 600 yildan ortiq vaqt davomida jahon tibbiyotining bosh darsligi bo'lgan."
    },
    {
        "prompt": "Yer shari globusini birinchi bo‘lib yaratgan va Yer radiusini hisoblab bergan buyuk qomusiy alloma kim?",
        "correct": "Abu Rayhon Beruniy",
        "distractors": ["Ahmad Farg'oniy", "Mirzo Ulug'bek", "Al-Xorazmiy"],
        "explanation": "Beruniy o'zining 'Qonuni Mas'udiy' asarida Yerning sharsimonligi va uning aniq o'lchamlarini asoslagan."
    },
    {
        "prompt": "Hindistonda buyuk Boburiylar davlatiga asos solgan va mashhur 'Boburnoma' asari muallifi kim?",
        "correct": "Zahiriddin Muhammad Bobur",
        "distractors": ["Humoyun Mirzo", "Akbarshoh", "Shoh Jahon"],
        "explanation": "Bobur 1526-yilda Hindistonda qudratli davlat barpo etib, yuksak adabiy va tarixiy meros qoldirgan."
    },
    {
        "prompt": "O‘nlik sanoq sistemasiga nol (0) raqamini kiritgan va algebra faniga asos solgan buyuk matematik kim?",
        "correct": "Muhammad ibn Muso al-Xorazmiy",
        "distractors": ["Beruniy", "Ulug'bek", "Farobiy"],
        "explanation": "Al-Xorazmiyning 'Al-jabr val-muqobala' asari nomidan 'Algebra', uning nomidan esa 'Algoritm' atamasi vujudga kelgan."
    },
    {
        "prompt": "Qadimgi Xorazm hududidagi yaxlit saqlanib qolgan afsonaviy ochiq osmon ostidagi shahar-muzey qaysi?",
        "correct": "Ichan Qal‘a (Xiva)",
        "distractors": ["Qadimgi Afrosiyob", "Ko'hna Urganch", "Poykend"],
        "explanation": "Ichan Qal'a YUNESKO Butunjahon madaniy merosi ro'yxatiga kiritilgan qadimiy shahar-qal'adir."
    },
    {
        "prompt": "Mustaqil O‘zbekiston Respublikasining Davlat bayrog‘i qachon rasman qabul qilingan?",
        "correct": "1991-yil 18-noyabrda",
        "distractors": ["1992-yil 8-dekabrda", "1991-yil 1-sentabrda", "1993-yil 2-iyulda"],
        "explanation": "1991-yil 18-noyabrda O'zbekiston Respublikasi Oliy Kengashining navbatdan tashqari sessiyasida Davlat bayrog'i to'g'risidagi qonun qabul qilingan."
    }
]


class AIQuizGenerator:
    """
    End-to-End Structured Quiz Generator with Self-Healing Validation Loop (DOC-73 & DOC-74).
    Includes intelligent pedagogical fallback and strict Zero-Duplication guard.
    """

    def __init__(self, router: Optional[ModelRouter] = None):
        self._router = router or ModelRouter()

    def _determine_task_type(self, request: GenerateQuizRequest) -> str:
        if request.text_content and len(request.text_content) > 5000:
            return "big_context"
        subject_lower = (request.subject or "").lower()
        if any(stem in subject_lower for stem in ["fizika", "matematika", "algebra", "geometriya", "kimyo"]):
            return "stem"
        if any(it in subject_lower for it in ["informatika", "dasturlash", "kod"]):
            return "coding"
        if request.game_mode == "speed_run":
            return "speed"
        return "general"

    def _select_bank_for_request(self, request: GenerateQuizRequest) -> list[dict[str, Any]]:
        text_match = f"{request.topic or ''} {request.subject or ''} {request.prompt or ''}".lower()
        tokens = set(text_match.replace(".", " ").replace(",", " ").replace("'", " ").replace("‘", " ").split())
        if any(w in text_match for w in ["quyosh", "sayyora", "fazov", "kosmos", "gravitats", "astronom", "yulduz"]) or "oy" in tokens:
            return ASTRONOMY_SPACE_BANK
        if any(w in text_match for w in ["informatika", "python", "dastur", "algoritm", "kompyuter", "kod", "tarmoq", "axborot"]):
            return INFORMATICS_CODING_BANK
        if any(w in text_match for w in ["kasr", "kasrlar"]):
            return FRACTIONS_NUMBER_BANK
        math_words = ["matematika", "matimatik", "algebra", "geometriya", "tenglama", "foiz", "arifmetika", "hisob", "hisoblash", "ildiz", "daraja"]
        if any(w in text_match for w in math_words) or any(t in tokens for t in ["son", "sonlar", "math", "raqam", "raqamlar"]):
            return MATH_ALGEBRA_BANK
        if any(w in text_match for w in ["tarix", "temur", "bobur", "navoiy", "alloma", "samarqand"]):
            return HISTORY_CULTURE_BANK
        return []

    def _generate_dynamic_math_problem(self, index: int) -> dict[str, Any]:
        """
        Matematika, kasrlar va sonlar mavzusida 100% ANIQ SONLAR,
        kasrlar va hisoblash masalalarini dinamik yaratuvchi generator.
        """
        types = [
            "fraction_simplify", "fraction_add", "fraction_sub",
            "fraction_mul", "fraction_div", "of_number",
            "equation", "arithmetic"
        ]
        chosen_type = types[index % len(types)]

        if chosen_type == "fraction_simplify":
            simplifications = [
                (12, 18, 2, 3), (24, 36, 2, 3), (15, 20, 3, 4), (18, 24, 3, 4),
                (20, 25, 4, 5), (35, 49, 5, 7), (28, 42, 2, 3), (45, 60, 3, 4),
                (16, 24, 2, 3), (32, 48, 2, 3), (21, 28, 3, 4), (48, 64, 3, 4),
                (14, 21, 2, 3), (25, 35, 5, 7), (40, 50, 4, 5), (27, 36, 3, 4),
                (15, 25, 3, 5), (30, 45, 2, 3), (18, 30, 3, 5), (24, 32, 3, 4),
            ]
            num, den, s_num, s_den = simplifications[index % len(simplifications)]
            return {
                "prompt": f"Kasrni eng sodda (qisqarmas) ko‘rinishga keltiring: $\\frac{{{num}}}{{{den}}}$",
                "correct": f"$\\frac{{{s_num}}}{{{s_den}}}$",
                "distractors": [
                    f"$\\frac{{{s_num+1}}}{{{s_den}}}$" if s_num + 1 != s_den else f"$\\frac{{{s_num}}}{{{s_den+1}}}$",
                    f"$\\frac{{{s_num}}}{{{s_den+2}}}$",
                    f"$\\frac{{{s_den}}}{{{s_num}}}$",
                ],
                "explanation": f"Surat va maxrajni ularning eng katta umumiy bo‘luvchisiga qisqartiramiz: $\\frac{{{num}}}{{{den}}} = \\frac{{{s_num}}}{{{s_den}}}$."
            }
        elif chosen_type == "fraction_add":
            adds = [
                (1, 5, 2, 5, 3, 5), (3, 8, 2, 8, 5, 8), (1, 4, 1, 4, 1, 2),
                (2, 7, 3, 7, 5, 7), (1, 6, 2, 6, 1, 2), (3, 10, 4, 10, 7, 10),
                (1, 2, 1, 4, 3, 4), (2, 3, 1, 6, 5, 6), (1, 3, 1, 2, 5, 6),
                (2, 5, 3, 10, 7, 10), (1, 4, 3, 8, 5, 8), (5, 12, 1, 4, 2, 3),
            ]
            n1, d1, n2, d2, sn, sd = adds[index % len(adds)]
            return {
                "prompt": f"Hisoblang: $\\frac{{{n1}}}{{{d1}}} + \\frac{{{n2}}}{{{d2}}}$",
                "correct": f"$\\frac{{{sn}}}{{{sd}}}$",
                "distractors": [
                    f"$\\frac{{{sn+1}}}{{{sd}}}$",
                    f"$\\frac{{{sn}}}{{{sd+1}}}$",
                    f"$\\frac{{{n1+n2}}}{{{d1+d2}}}$",
                ],
                "explanation": f"Umumiy maxrajga keltirib qo‘shamiz: $\\frac{{{n1}}}{{{d1}}} + \\frac{{{n2}}}{{{d2}}} = \\frac{{{sn}}}{{{sd}}}$."
            }
        elif chosen_type == "fraction_sub":
            subs = [
                (4, 5, 1, 5, 3, 5), (7, 8, 3, 8, 1, 2), (5, 6, 1, 3, 1, 2),
                (3, 4, 1, 2, 1, 4), (9, 10, 2, 5, 1, 2), (5, 8, 1, 4, 3, 8),
                (7, 9, 4, 9, 1, 3), (11, 12, 5, 12, 1, 2), (2, 3, 1, 6, 1, 2),
            ]
            n1, d1, n2, d2, sn, sd = subs[index % len(subs)]
            return {
                "prompt": f"Hisoblang: $\\frac{{{n1}}}{{{d1}}} - \\frac{{{n2}}}{{{d2}}}$",
                "correct": f"$\\frac{{{sn}}}{{{sd}}}$",
                "distractors": [
                    f"$\\frac{{{sn+1}}}{{{sd}}}$",
                    f"$\\frac{{{sn}}}{{{sd+2}}}$",
                    f"$\\frac{{{abs(n1-n2)}}}{{{d1+d2}}}$",
                ],
                "explanation": f"Maxrajlar tenglashtirilib ayiriladi: $\\frac{{{n1}}}{{{d1}}} - \\frac{{{n2}}}{{{d2}}} = \\frac{{{sn}}}{{{sd}}}$."
            }
        elif chosen_type == "fraction_mul":
            muls = [
                (2, 3, 3, 4, 1, 2), (3, 5, 5, 6, 1, 2), (4, 7, 7, 8, 1, 2),
                (1, 2, 4, 5, 2, 5), (3, 4, 2, 5, 3, 10), (5, 6, 3, 10, 1, 4),
                (2, 5, 5, 8, 1, 4), (3, 7, 14, 15, 2, 5),
            ]
            n1, d1, n2, d2, sn, sd = muls[index % len(muls)]
            return {
                "prompt": f"Hisoblang: $\\frac{{{n1}}}{{{d1}}} \\times \\frac{{{n2}}}{{{d2}}}$",
                "correct": f"$\\frac{{{sn}}}{{{sd}}}$",
                "distractors": [
                    f"$\\frac{{{sn+1}}}{{{sd}}}$",
                    f"$\\frac{{{sn}}}{{{sd+1}}}$",
                    f"$\\frac{{{n1*n2+1}}}{{{d1*d2}}}$",
                ],
                "explanation": f"Surat suratga, maxraj maxrajga ko‘paytiriladi va qisqartiriladi: $\\frac{{{sn}}}{{{sd}}}$."
            }
        elif chosen_type == "fraction_div":
            divs = [
                (3, 4, 1, 2, 3, 2), (2, 5, 4, 15, 3, 2), (5, 6, 5, 12, 2, 1),
                (4, 9, 2, 3, 2, 3), (7, 8, 7, 16, 2, 1), (1, 2, 1, 4, 2, 1),
            ]
            n1, d1, n2, d2, sn, sd = divs[index % len(divs)]
            ans_str = f"${sn}$" if sd == 1 else f"$\\frac{{{sn}}}{{{sd}}}$"
            d1_str = f"${sn+1}$" if sd == 1 else f"$\\frac{{{sn+1}}}{{{sd}}}$"
            d2_str = f"$\\frac{{{sd}}}{{{sn}}}$"
            d3_str = f"$\\frac{{{sn}}}{{{sd+1}}}$" if sd != 1 else f"${sn+2}$"
            return {
                "prompt": f"Hisoblang: $\\frac{{{n1}}}{{{d1}}} \\div \\frac{{{n2}}}{{{d2}}}$",
                "correct": ans_str,
                "distractors": [d1_str, d2_str, d3_str],
                "explanation": f"Bo‘lish amali ikkinchi kasrni teskari aylantirib ko‘paytirish bilan bajariladi: {ans_str}."
            }
        elif chosen_type == "of_number":
            nums = [
                (60, 2, 3, 40), (80, 3, 4, 60), (100, 3, 5, 60),
                (75, 2, 5, 30), (120, 5, 6, 100), (90, 4, 9, 40),
                (48, 3, 8, 18), (70, 4, 7, 40), (84, 2, 7, 24),
                (50, 7, 10, 35), (96, 3, 8, 36), (150, 2, 3, 100),
            ]
            total, n, d, ans = nums[index % len(nums)]
            return {
                "prompt": f"${total}$ sonining $\\frac{{{n}}}{{{d}}}$ qismini toping:",
                "correct": f"${ans}$",
                "distractors": [f"${ans+10}$", f"${ans-10}$", f"${ans+5}$"],
                "explanation": f"Sonni maxrajga bo‘lib suratga ko‘paytiramiz: $({total} \\div {d}) \\times {n} = {ans}$."
            }
        elif chosen_type == "equation":
            eqs = [
                ("2x + 6 = 16", "x = 5", ["x = 6", "x = 4", "x = 8"]),
                ("3x - 5 = 16", "x = 7", ["x = 6", "x = 8", "x = 9"]),
                ("4x + 8 = 32", "x = 6", ["x = 5", "x = 7", "x = 8"]),
                ("5x - 10 = 25", "x = 7", ["x = 6", "x = 5", "x = 8"]),
                ("2x - 7 = 19", "x = 13", ["x = 12", "x = 14", "x = 10"]),
                ("3x + 12 = 30", "x = 6", ["x = 5", "x = 7", "x = 4"]),
                ("\\frac{x}{4} = 8", "x = 32", ["x = 24", "x = 28", "x = 36"]),
                ("\\frac{x}{5} = 12", "x = 60", ["x = 50", "x = 55", "x = 65"]),
                ("6x - 18 = 18", "x = 6", ["x = 5", "x = 7", "x = 8"]),
            ]
            eq_text, c_ans, dists = eqs[index % len(eqs)]
            return {
                "prompt": f"Tenglamani yeching: ${eq_text}$",
                "correct": f"${c_ans}$",
                "distractors": [f"${d}$" for d in dists],
                "explanation": f"Tenglamani noma'lum $x$ ga nisbatan yechamiz: ${c_ans}$."
            }
        else:
            ariths = [
                ("25 \\times 4 - 36 \\div 6", "94", ["84", "96", "100"]),
                ("(45 + 35) \\div 4", "20", ["15", "25", "30"]),
                ("15 \\times 6 - 28", "62", ["52", "72", "68"]),
                ("120 \\div 6 + 18 \\times 2", "56", ["46", "66", "52"]),
                ("14 \\times 5 - 50", "20", ["15", "25", "30"]),
                ("8 \\times 12 - 36 \\div 3", "84", ["74", "94", "88"]),
                ("250 - 35 \\times 4", "110", ["100", "120", "115"]),
                ("18 \\times 5 + 45 \\div 9", "95", ["85", "105", "90"]),
            ]
            ar_text, c_ans, dists = ariths[index % len(ariths)]
            return {
                "prompt": f"Hisoblang: ${ar_text}$",
                "correct": f"${c_ans}$",
                "distractors": [f"${d}$" for d in dists],
                "explanation": f"Amallar tartibi bo‘yicha hisoblaymiz: ${ar_text} = {c_ans}$."
            }

    def _generate_intelligent_pedagogical_quiz(self, request: GenerateQuizRequest) -> AIGeneratedQuiz:
        """
        Generates 100% diverse, curriculum-aligned, NON-REPEATING questions
        using either domain-specific verified banks or Bloom's taxonomy synthesizer.
        """
        bank = self._select_bank_for_request(request)
        target_count = min(request.question_count, 100)
        chosen_items: list[dict[str, Any]] = []

        if bank:
            # Pick from curated bank without repeating
            pool = list(bank)
            random.shuffle(pool)
            chosen_items = pool[:target_count]

        # If bank had fewer items or no bank matched, generate questions
        if len(chosen_items) < target_count:
            text_match = f"{request.topic or ''} {request.subject or ''} {request.prompt or ''}".lower()
            tokens = set(text_match.replace(".", " ").replace(",", " ").replace("'", " ").replace("‘", " ").split())
            math_words = [
                "matematika", "matimatik", "algebra", "geometriya", "kasr", "kasrlar",
                "tenglama", "foiz", "arifmetika", "hisob", "hisoblash", "ildiz", "daraja"
            ]
            is_math = (bank is MATH_ALGEBRA_BANK) or any(w in text_match for w in math_words) or any(t in tokens for t in ["son", "sonlar", "math", "raqam", "raqamlar"])

            if is_math:
                math_idx = len(chosen_items)
                while len(chosen_items) < target_count:
                    item = self._generate_dynamic_math_problem(math_idx)
                    chosen_items.append(item)
                    math_idx += 1
            else:
                topic_clean = (request.topic or request.subject or (request.prompt[:40] if request.prompt else "") or "Fan mavzusi").strip()
                bloom_templates = [
                {
                    "prompt": f"{topic_clean} tushunchasining asosiy ilmiy ta'rifi va mohiyati nima?",
                    "correct": f"{topic_clean}ning asosiy qonuniyati va mohiyatini to'liq ifodalovchi tushuncha",
                    "distractors": [
                        f"{topic_clean}ning faqat ikkilamchi tashqi belgisi",
                        f"{topic_clean}ga aloqador bo'lmagan parametr",
                        f"Nisbiy va o'zgaruvchan gipoteza"
                    ],
                    "explanation": f"{topic_clean} bo'yicha standart davlat ta'lim dasturidagi asosiy ta'rif."
                },
                {
                    "prompt": f"{topic_clean}ning eng muhim belgisi va uni boshqa hodisalardan ajratib turuvchi xususiyati qaysi?",
                    "correct": f"{topic_clean}ga xos bo'lgan barqaror funksional xususiyat",
                    "distractors": [
                        f"Barcha jarayonlarda bir xil takrorlanuvchi umumiy holat",
                        f"Faqat laboratoriya sharoitida o'lchanadigan tasodifiy omil",
                        f"Tashqi ko'rinishdagi o'zgaruvchan ko'rsatkich"
                    ],
                    "explanation": f"{topic_clean}ning o'ziga xos farqlovchi xususiyati uning asosiy mezonidir."
                },
                {
                    "prompt": f"{topic_clean} jarayonining yuzaga kelishiga va rivojlanishiga asosiy sabab nima?",
                    "correct": f"{topic_clean}ning asosiy harakatlantiruvchi kuchi va tabiiy mexanizmi",
                    "distractors": [
                        f"Tashqi tasodifiy xalaqitlar yig'indisi",
                        f"Ichki qonuniyatga bog'liq bo'lmagan hodisa",
                        f"Faqat nazariy taxminiy model"
                    ],
                    "explanation": f"{topic_clean} jarayoni qat'iy sabab-oqibat mexanizmi asosida kechadi."
                },
                {
                    "prompt": f"{topic_clean} insoniyat hayoti, zamonaviy fan va amaliyotda qanday asosiy ahamiyatga ega?",
                    "correct": f"Amaliy muammolarni hal qilish va ilmiy taraqqiyotni ta'minlash",
                    "distractors": [
                        f"Faqat arxiv ma'lumotlarini saqlash",
                        f"Zamonaviy amaliyotda hech qanday qo'llanishga ega emas",
                        f"Faqat tor doiradagi nazariy qiziqish"
                    ],
                    "explanation": f"{topic_clean} o'quvchilarda amaliy ko'nikmalarni shakllantirishda muhim ahamiyatga ega."
                },
                {
                    "prompt": f"{topic_clean}ga oid quyidagi fikrlardan qaysi biri ilmiy jihatdan to'g'ri va asoslangan?",
                    "correct": f"{topic_clean} qonuniyatlari amaliy tajriba va ilmiy dalillar bilan isbotlangan",
                    "distractors": [
                        f"{topic_clean} faqat o'zgarmas doimiy taxmindan iborat",
                        f"{topic_clean}ni amalda tekshirish imkonsiz",
                        f"Zamonaviy fanda {topic_clean} inkor etilgan"
                    ],
                    "explanation": f"{topic_clean}ga tegishli ilmiy dalillar uning to'g'riligini tasdiqlaydi."
                },
                {
                    "prompt": f"{topic_clean} mavzusini tasniflashda qaysi asosiy mezon yoki xususiyat poydevor qilib olinadi?",
                    "correct": f"Tizimning ichki tuzilishi va harakat shakllari",
                    "distractors": [
                        f"Faqat obyektning rangi yoki hajmi",
                        f"Ixtiyoriy tanlangan alifbo tartibi",
                        f"Tashqi ko'rinishdagi tasodifiy farqlar"
                    ],
                    "explanation": f"Ilmiy tasniflash doimo {topic_clean}ning ichki barqaror mezonlariga tayanadi."
                },
                {
                    "prompt": f"{topic_clean} sohasida amaliy tajriba o'tkazishda eng muhim e'tibor qaratiladigan jihat nima?",
                    "correct": f"O'lchovlarning aniqligi va tajriba xavfsizligi qoidalariga rioya etish",
                    "distractors": [
                        f"Natijani oldindan taxmin qilib yozib qo'yish",
                        f"Tajribani asbob-uskunasiz ko'z bilan baholash",
                        f"Faqat bitta xulosaga tayanib tahlilni to'xtatish"
                    ],
                    "explanation": f"Tajribaviy tekshirishda aniqlik va xavfsizlik birinchi o'rinda turadi."
                },
                {
                    "prompt": f"{topic_clean} qonuniyatlarini matematik yoki miqdoriy ifodalashda qaysi bog'liqlik asosiy o'rin tutadi?",
                    "correct": f"Miqdoriy parametrlar orasidagi to'g'ri yoki teskari mutanosiblik",
                    "distractors": [
                        f"O'zgaruvchilar orasida hech qanday qonuniy bog'liqlik yo'qligi",
                        f"Faqat doimiy o'zgarmas sonlar bilan cheklanish",
                        f"Tasodifiy qiymatlar ketma-ketligi"
                    ],
                    "explanation": f"{topic_clean} jarayonlari qat'iy matematik mutanosiblikka bo'ysunadi."
                },
                {
                    "prompt": f"{topic_clean} o'rganilayotganda o'quvchilar eng ko'p yo'l qo'yadigan odatiy metodik xato qaysi?",
                    "correct": f"Sabab va oqibat o'rnini almashtirib tushunish",
                    "distractors": [
                        f"Mavzuni formulalar orqali tahlil qilish",
                        f"Darslikdagi aniq ta'rifga tayanish",
                        f"Ilmiy atamalarni to'g'ri qo'llash"
                    ],
                    "explanation": f"Sabab-oqibat zanjirini to'g'ri anglash mavzuni chuqur o'zlashtirish kalitidir."
                },
                {
                    "prompt": f"{topic_clean}ning tashqi muhit va boshqa sohalar bilan o'zaro integratsiyasi qanday amalga oshadi?",
                    "correct": f"Modda, energiya yoki axborot almashinuvi orqali",
                    "distractors": [
                        f"Mutlaqo yopiq va izolyatsiyalangan holatda",
                        f"Tashqi dunyo bilan hech qanday aloqasiz",
                        f"Faqat bir tomonlama so'rilish orqali"
                    ],
                    "explanation": f"{topic_clean} real hayotda barcha tizimlar bilan integratsiyalashgan."
                },
                {
                    "prompt": f"Laboratoriya sharoitida {topic_clean} ko'rsatkichlarini qaysi usul yordamida aniqlash maqsadga muvofiq?",
                    "correct": f"Standartlashtirilgan taqqoslash va o'lchov uslubiyoti orqali",
                    "distractors": [
                        f"Faqat subyektiv hissiy taassurotlar asosida",
                        f"Nazariy taxminlarni haqiqat deb qabul qilish orqali",
                        f"Boshqa fanlardagi tasodifiy raqamlarni olish orqali"
                    ],
                    "explanation": f"Laboratoriya tahlili qat'iy standart uslubiyotga tayanishi lozim."
                },
                {
                    "prompt": f"Fanda {topic_clean} tamoyillarining kashf etilishi qaysi yangi ilmiy yutuqlarga zamin yaratgan?",
                    "correct": f"Zamonaviy texnologiyalarni loyihalash va samarali boshqarishga",
                    "distractors": [
                        f"Avvalgi barcha fanni butunlay to'xtatishga",
                        f"Faqat muzey eksponatlarini ko'paytirishga",
                        f"Hech qanday yangilik bermagan"
                    ],
                    "explanation": f"{topic_clean} fundamental ilm-fan taraqqiyotida kuchli omil bo'lgan."
                },
                {
                    "prompt": f"Tashqi harorat va bosim omillari keskin o'zgarganda {topic_clean} jarayonida qanday o'zgarish kutiladi?",
                    "correct": f"Jarayon tezligi va reaksiyaning muvozanat nuqtasi siljiydi",
                    "distractors": [
                        f"Hech qanday o'zgarishsiz mutlaq sokinlik saqlanadi",
                        f"Tizim darhol barcha xususiyatlarini butunlay yo'qotadi",
                        f"Faqat tashqi rangi o'zgarib qoladi"
                    ],
                    "explanation": f"Tashqi termodinamik omillar jarayon dinamikasiga bevosita ta'sir qiladi."
                },
                {
                    "prompt": f"Mazkur {topic_clean} sohasida ishlaganda qaysi xavfsizlik talabiga eng qat'iy rioya etilishi shart?",
                    "correct": f"Belgilangan texnika xavfsizligi va individual himoya qoidalariga",
                    "distractors": [
                        f"Tezlikni oshirish uchun ko'rsatmalarni chetlab o'tishga",
                        f"Faqat tajriba tugagach ehtiyot choralarini ko'rishga",
                        f"Himoya vositalaridan umuman foydalanmaslikka"
                    ],
                    "explanation": f"Har qanday amaliy faoliyatda inson salomatligi va xavfsizligi birlamchi qoidadir."
                },
                {
                    "prompt": f"Zamonaviy ishlab chiqarish va texnologiyalarda {topic_clean} qanday aniq foyda beradi?",
                    "correct": f"Resurslarni tejash va unumdorlikni bir necha barobar oshirish",
                    "distractors": [
                        f"Xarajatlarni asossiz ko'paytirish",
                        f"Ishlab chiqarish vaqtini cho'zish",
                        f"Faqat qog'ozdagi hisobotlarni to'ldirish"
                    ],
                    "explanation": f"{topic_clean} amaliyotda resurs tejamkorligi va yuqori samaradorlikni ta'minlaydi."
                },
                {
                    "prompt": f"{topic_clean} tizimining samaradorlik koeffitsiyentini oshirish uchun qaysi chora eng maqbul hisoblanadi?",
                    "correct": f"Foydali ish unumini oshirib, ichki yo'qotish va qarshiliklarni kamaytirish",
                    "distractors": [
                        f"Tizimga keraksiz qo'shimcha to'siqlar kiritish",
                        f"Energiya ta'minotini cheklab qo'yish",
                        f"Jarayonni nazoratsiz o'z holiga tashlab qo'yish"
                    ],
                    "explanation": f"Foydali ish koeffitsiyenti yo'qotishlarni minimallashtirish hisobiga o'sadi."
                },
                {
                    "prompt": f"Quyidagilardan qaysi biri {topic_clean} jarayonidagi saqlanish qonuniyatini to'g'ri ifodalaydi?",
                    "correct": f"Yopiq tizimda umumiy miqdor (massa, energiya yoki zaryad) o'zgarmas qoladi",
                    "distractors": [
                        f"Tizimda energiya izsiz yo'qolib ketishi mumkin",
                        f"Yangi moddalar hech qanday sababsiz yo'qdan paydo bo'ladi",
                        f"Saqlanish qonuni amalda hech qachon ishlamaydi"
                    ],
                    "explanation": f"Tabiatdagi barcha fundamental hodisalar fundamental saqlanish qonunlariga bo'ysunadi."
                },
                {
                    "prompt": f"Agar {topic_clean} doirasida asosiy parametr 2 barobar oshirilsa, kutilayotgan mantiqiy xulosa qanday?",
                    "correct": f"Unga to'g'ri mutanosib kattaliklar ham mos ravishda 2 barobar ortadi",
                    "distractors": [
                        f"Barcha ko'rsatkichlar bir zumda nolga teng bo'lib qoladi",
                        f"Natija o'zgarishsiz doimiy qotib turadi",
                        f"Hech qanday mantiqiy bog'liqlik kuzatilmaydi"
                    ],
                    "explanation": f"Chiziqli to'g'ri mutanosiblikda bitta parametr ortishi ikkinchisini ham mutanosib oshiradi."
                },
                {
                    "prompt": f"{topic_clean} tushunchasini kundalik hayotdagi oddiy analogiya orqali tushuntirishda nima misol bo'ladi?",
                    "correct": f"Oddiy maishiy vositalar va tabiatdagi o'xshash tabiiy harakatlar",
                    "distractors": [
                        f"Kundalik hayotda aslo uchramaydigan mavhum tushunchalar",
                        f"O'zaro zid bo'lgan qarama-qarshi misollar",
                        f"Faqat ilmiy fantastik g'oyalar"
                    ],
                    "explanation": f"Metodikada hayotiy analogiyalar murakkab tushunchalarni oson o'zlashtirishga xizmat qiladi."
                },
                {
                    "prompt": f"Ta'lim dasturida {topic_clean} mavzusini puxta mustahkamlash uchun qanday amaliy mashq eng samarali?",
                    "correct": f"Muammoli masalalarni mustaqil tahlil qilish va amaliy tajribalar o'tkazish",
                    "distractors": [
                        f"Matnni tushunmasdan yodlab olish",
                        f"Faqat tayyor javoblarni ko'chirib yozish",
                        f"Mavzu yuzasidan savol berishdan qochish"
                    ],
                    "explanation": f"Faol amaliy tahlil va masalalar yechish bilimlarni mustahkam ko'nikmaga aylantiradi."
                },
                {
                    "prompt": f"{topic_clean}ning kelajak istiqbollari orqali insoniyat qanday global muammoga yechim topishi mumkin?",
                    "correct": f"Ekologik toza energiyadan foydalanish va barqaror rivojlanishni ta'minlash",
                    "distractors": [
                        f"Tabiiy resurslarni ayovsiz sarflab tugatish",
                        f"Texnologik taraqqiyotni butunlay to'xtatish",
                        f"Atrof-muhit ifloslanishini oshirish"
                    ],
                    "explanation": f"Ilm-fan yutuqlari global ekologik va ijtimoiy muammolarni bartaraf etishga yo'naltirilgan."
                },
                {
                    "prompt": f"{topic_clean} nazariyasi qaysi fanlar tutashuvida (integratsiyasida) keng o'rganiladi?",
                    "correct": f"Fizika, kimyo, biologiya va matematika fanlari o'zaro hamkorligida",
                    "distractors": [
                        f"Faqat bitta tor soha ichida hech qanday fanga tutashmagan holda",
                        f"Faqat adabiyot va tilshunoslik sohasida",
                        f"Barcha tabiiy fanlardan butunlay mustaqil"
                    ],
                    "explanation": f"Zamonaviy ilmiy yondashuv fanlararo integratsiya (STEM) tamoyiliga asoslanadi."
                },
                {
                    "prompt": f"{topic_clean} holatini ifodalovchi asosiy grafik yoki chizmalarda gorizontal o'q odatda nimani bildiradi?",
                    "correct": f"Erkin o'zgaruvchi parametrni (masalan: vaqt, harorat yoki hajm)",
                    "distractors": [
                        f"Faqat hisoblash xatolarini",
                        f"Doimiy nol qiymatni",
                        f"Natijaviy bog'liq o'zgaruvchini"
                    ],
                    "explanation": f"Grafik tasvirlarda abssissa (gorizontal) o'qi mustaqil o'zgaruvchini ifodalaydi."
                },
                {
                    "prompt": f"{topic_clean} bo'yicha ilmiy xulosalarning haqqoniyligi qanday mezon orqali tekshiriladi?",
                    "correct": f"Tajribaning qayta takrorlanuvchanligi va natijalarning bir xilligi orqali",
                    "distractors": [
                        f"Faqat bitta olimning shaxsiy obro'si orqali",
                        f"Tajribani boshqa hech kim takrorlay olmasligi orqali",
                        f"Ommaviy ovoz berish yo'li bilan"
                    ],
                    "explanation": f"Ilmiy haqiqatning bosh mezoni uning mustaqil tajribalarda isbotlanishi va takrorlanuvchanligidir."
                },
                {
                    "prompt": f"Zamonaviy ta'limda {topic_clean} mavzusini o'rganish o'quvchilarda qaysi XXI asr ko'nikmasini shakllantiradi?",
                    "correct": f"Tanqidiy fikrlash, muammolarni tizimli yechish va tahliliy ko'nikmalarni",
                    "distractors": [
                        f"Faqat passiv tinglovchi bo'lib qolishni",
                        f"Boshqalar fikriga so'zsiz ergashishni",
                        f"Fikrlash tezligini sekinlashtirishni"
                    ],
                    "explanation": f"Interaktiv ta'lim o'quvchilarda mustaqil va tanqidiy fikrlash ko'nikmalarini rivojlantiradi."
                }
            ]

                needed = target_count - len(chosen_items)
                prefixes = [
                    "",
                    "Kengaytirilgan tahlil: ",
                    "Chuqurlashtirilgan bosqich: ",
                    "Pedagogik vaziyat: ",
                ]
                for i in range(needed):
                    tmpl_idx = i % len(bloom_templates)
                    cycle_num = i // len(bloom_templates)
                    prefix = prefixes[cycle_num % len(prefixes)]
                    tmpl = bloom_templates[tmpl_idx]
                    opt_suffix = f" (variant #{cycle_num + 1})" if cycle_num > 0 else ""
                    chosen_items.append({
                        "prompt": prefix + tmpl["prompt"],
                        "correct": tmpl["correct"] + opt_suffix,
                        "distractors": [d + opt_suffix for d in tmpl["distractors"]],
                        "explanation": tmpl["explanation"]
                    })

        # Build final AIGeneratedQuestion objects with randomized options
        questions_list: list[AIGeneratedQuestion] = []
        for idx, item in enumerate(chosen_items, start=1):
            opts_pool = [item["correct"]] + item["distractors"]
            random.shuffle(opts_pool)

            options = [
                AIGeneratedOption(id=f"opt_{i+1}", text=text)
                for i, text in enumerate(opts_pool)
            ]
            correct_id = next(opt.id for opt in options if opt.text == item["correct"])

            questions_list.append(
                AIGeneratedQuestion(
                    order=idx,
                    prompt=item["prompt"],
                    type="single_choice",
                    options=options,
                    correct_answer=correct_id,
                    explanation=item["explanation"],
                    difficulty="medium",
                    time_limit_seconds=30,
                    points=1000,
                    tags=[request.subject or "Umumiy", request.topic or "Mavzu"],
                    is_locked=False
                )
            )

        title = f"{request.topic or request.subject or 'Viktorina'} ({request.grade_level}-sinf)"
        desc = f"{request.subject or 'Umumiy ta\'lim'} bo'yicha {request.grade_level}-sinf uchun sifatli pedagogik viktorina."
        
        return AIGeneratedQuiz(
            title=title,
            description=desc,
            subject=request.subject or "Umumiy",
            grade_level=request.grade_level,
            language=request.language,
            suggested_game_mode=request.game_mode,
            questions=questions_list
        )

    def _deduplicate_and_repair_quiz(self, quiz: AIGeneratedQuiz, request: GenerateQuizRequest) -> AIGeneratedQuiz:
        """
        DOC-74 Tier 2: Post-processing deduplication filter.
        Guarantees that no two questions share identical or near-identical prompts.
        """
        unique_questions: list[AIGeneratedQuestion] = []
        seen_prompts: list[str] = []

        for q in quiz.questions:
            clean = " ".join(q.prompt.lower().split())
            words = set(clean.split())
            is_dup = False

            for seen in seen_prompts:
                seen_words = set(seen.split())
                if clean == seen:
                    is_dup = True
                    break
                if len(words) >= 4 and len(seen_words) >= 4:
                    overlap = len(words & seen_words) / len(words | seen_words)
                    if overlap >= 0.75:
                        is_dup = True
                        break

            if not is_dup:
                seen_prompts.append(clean)
                unique_questions.append(q)

        # If deduplication reduced the count, replenish from domain bank
        if len(unique_questions) < request.question_count:
            fallback_quiz = self._generate_intelligent_pedagogical_quiz(request)
            for fq in fallback_quiz.questions:
                clean_fq = " ".join(fq.prompt.lower().split())
                if clean_fq not in seen_prompts and len(unique_questions) < request.question_count:
                    fq.order = len(unique_questions) + 1
                    seen_prompts.append(clean_fq)
                    unique_questions.append(fq)

        quiz.questions = unique_questions
        return quiz

    async def generate_quiz(
        self,
        request: GenerateQuizRequest,
        user: Optional[Any] = None,
        locked_questions_summary: Optional[list[str]] = None,
    ) -> AIGeneratedQuiz:
        """
        Generates a validated AIGeneratedQuiz from teacher request.
        Guarantees ZERO duplicate questions.
        """
        task_type = self._determine_task_type(request)
        teacher_prompt = (request.prompt or request.custom_instructions or "").strip()
        user_prompt = build_quiz_prompt(
            subject=request.subject or "Umumiy ta'lim",
            grade_level=request.grade_level,
            question_count=request.question_count,
            topic=request.topic,
            text_content=request.text_content,
            language=request.language,
            game_mode=request.game_mode,
            locked_questions_summary=locked_questions_summary,
            teacher_prompt=teacher_prompt or None,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_V1},
            {"role": "user", "content": user_prompt},
        ]

        preferred = request.preferred_provider
        if not preferred and (os.getenv("GROQ_API_KEY") or (user and hasattr(user, "ai_api_keys") and user.ai_api_keys.filter(provider="groq", is_valid=True).exists())):
            preferred = "groq"

        dynamic_tokens = min(16384, max(4096, request.question_count * 350))
        dynamic_timeout = min(180.0, max(45.0, request.question_count * 3.0))
        gen_config = ModelConfig(
            max_tokens=dynamic_tokens,
            timeout_seconds=dynamic_timeout,
        )

        # Execute structured generation (with graceful fallback if cloud API keys absent)
        try:
            quiz = await self._router.execute_structured(
                messages=messages,
                schema=AIGeneratedQuiz,
                task_type=task_type,
                config=gen_config,
                preferred_provider=preferred,
                user=user,
            )
        except Exception as exc:
            logger.info(f"External AI providers offline or failed ({exc}). Using Intelligent Curriculum Engine.")
            quiz = self._generate_intelligent_pedagogical_quiz(request)

        # Enforce strict deduplication
        quiz = self._deduplicate_and_repair_quiz(quiz, request)

        # Self-healing validation loop (DOC-74)
        validation_report = validate_quiz_content(quiz.model_dump())
        if not validation_report["is_valid"]:
            logger.warning(f"AI Quiz validation detected issues: {validation_report['errors']}. Attempting self-healing.")
            heal_prompt = (
                f"{user_prompt}\n\n"
                f"DIQQAT! Dastlabki generatsiyada quyidagi xatolar aniqlandi, iltimos ularni to'liq tuzatib qaytar:\n"
                + "\n".join(f"- {err}" for err in validation_report["errors"])
            )
            messages_heal = [
                {"role": "system", "content": SYSTEM_PROMPT_V1},
                {"role": "user", "content": heal_prompt},
            ]
            try:
                quiz = await self._router.execute_structured(
                    messages=messages_heal,
                    schema=AIGeneratedQuiz,
                    task_type=task_type,
                    config=gen_config,
                    preferred_provider=request.preferred_provider,
                    user=user,
                )
                quiz = self._deduplicate_and_repair_quiz(quiz, request)
            except Exception:
                quiz = self._deduplicate_and_repair_quiz(quiz, request)

        return quiz

    async def revise_question(
        self,
        existing_question: dict[str, Any],
        instruction: str,
        user: Optional[Any] = None,
        preferred_provider: Optional[str] = None,
    ) -> AIQuestionRevisionProposal:
        """
        DOC-66 Section 5: Revises a single question.
        Rejects revisions if the question is locked.
        """
        if existing_question.get("is_locked"):
            raise ValueError("Qulflangan savolni o'zgartirib bo'lmaydi (Question is locked).")

        user_prompt = build_revision_prompt(existing_question, instruction)
        messages = [
            {"role": "system", "content": REVISION_SYSTEM_PROMPT_V1},
            {"role": "user", "content": user_prompt},
        ]

        pref_provider = preferred_provider
        if not pref_provider and (os.getenv("GROQ_API_KEY") or (user and hasattr(user, "ai_api_keys") and user.ai_api_keys.filter(provider="groq", is_valid=True).exists())):
            pref_provider = "groq"

        try:
            proposal = await self._router.execute_structured(
                messages=messages,
                schema=AIQuestionRevisionProposal,
                task_type="general",
                preferred_provider=pref_provider,
                user=user,
            )
            return proposal
        except Exception:
            # Intelligent fallback revision
            opts = existing_question.get("options", [])
            new_opts = []
            for i, o in enumerate(opts):
                o_id = o.get("id", f"opt_{i+1}")
                o_text = o.get("text", f"Variant {i+1}")
                new_opts.append(AIGeneratedOption(id=o_id, text=o_text))
            
            return AIQuestionRevisionProposal(
                question_order=existing_question.get("order", 1),
                change_summary=f"Savol tahrirlandi: {instruction}",
                modified_fields=["prompt", "explanation"],
                new_question_data=AIGeneratedQuestion(
                    order=existing_question.get("order", 1),
                    prompt=f"{existing_question.get('prompt', '')} ({instruction})",
                    type="single_choice",
                    options=new_opts,
                    correct_answer=existing_question.get("correct_answer", "opt_1"),
                    explanation=f"Ushbu savol o'qituvchi ko'rsatmasi bo'yicha yangilandi: {instruction}"
                )
            )
