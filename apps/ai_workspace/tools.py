from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

FORBIDDEN_PHRASES = [
    "barchasi to'g'ri",
    "barchasi togri",
    "yuqoridagilarning barchasi",
    "hech biri to'g'ri emas",
    "hech biri togri emas",
    "a va b javoblar",
    "all of the above",
    "none of the above",
]


def validate_quiz_content(quiz_data: dict[str, Any]) -> dict[str, Any]:
    """
    DOC-74: Tier 1 Deterministic heuristic content validation.
    Checks answer key integrity, duplicate options, forbidden phrases, and length bias.
    """
    errors: list[str] = []
    warnings: list[str] = []

    questions = quiz_data.get("questions", [])
    if not questions:
        errors.append("Viktorinada kamida 1 ta savol bo'lishi shart.")

    seen_prompts: list[tuple[int, str]] = []

    for idx, q in enumerate(questions, start=1):
        prompt = q.get("prompt", "")
        options = q.get("options", [])
        correct_ans = q.get("correct_answer")

        # 0. Question Uniqueness & Anti-Duplication Check
        clean_p = " ".join(prompt.strip().lower().split())
        for prev_idx, prev_p in seen_prompts:
            if clean_p == prev_p:
                errors.append(f"{idx}-savol {prev_idx}-savol bilan aynan bir xil takrorlangan (Dublikat). Bitta savolni 2 marta qaytarish qat'iyan taqiqlanadi.")
            else:
                words_cur = set(clean_p.split())
                words_prev = set(prev_p.split())
                if len(words_cur) >= 4 and len(words_prev) >= 4:
                    overlap = len(words_cur & words_prev) / len(words_cur | words_prev)
                    if overlap >= 0.75:
                        errors.append(f"{idx}-savol va {prev_idx}-savol bir-biriga juda o'xshash (takrorlanuvchi savollar).")
        seen_prompts.append((idx, clean_p))

        # 1. Answer key integrity
        if options and q.get("type") in ("single_choice", "true_false", "multiple_choice"):
            opt_ids = {opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", None) for opt in options}
            if isinstance(correct_ans, str) and correct_ans not in opt_ids:
                errors.append(f"{idx}-savol: To'g'ri javob '{correct_ans}' variantlar ichida topilmadi.")
            elif isinstance(correct_ans, list):
                for ans in correct_ans:
                    if str(ans) not in opt_ids:
                        errors.append(f"{idx}-savol: To'g'ri javob '{ans}' variantlar ichida topilmadi.")

        # 2. Duplicate options
        opt_texts = [
            (opt.get("text", "").strip().lower() if isinstance(opt, dict) else getattr(opt, "text", "").strip().lower())
            for opt in options
        ]
        if len(opt_texts) != len(set(opt_texts)):
            errors.append(f"{idx}-savol: Variantlar orasida takrorlanish (dublikat) mavjud.")

        # 3. Forbidden phrases
        for opt_text in opt_texts:
            for forbidden in FORBIDDEN_PHRASES:
                if forbidden in opt_text:
                    errors.append(
                        f"{idx}-savol: Taqiqlangan variant iborasi aniqlandi: '{forbidden}'"
                    )

        # 4. Length bias check
        if len(options) >= 2 and isinstance(correct_ans, str):
            correct_opt = next(
                (opt for opt in options if (opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", None)) == correct_ans),
                None,
            )
            distractors = [
                opt for opt in options if (opt.get("id") if isinstance(opt, dict) else getattr(opt, "id", None)) != correct_ans
            ]
            if correct_opt and distractors:
                c_len = len(correct_opt.get("text", "") if isinstance(correct_opt, dict) else getattr(correct_opt, "text", ""))
                avg_d_len = sum(len(d.get("text", "") if isinstance(d, dict) else getattr(d, "text", "")) for d in distractors) / float(len(distractors))
                if avg_d_len > 0 and c_len >= (avg_d_len * 3.0):
                    warnings.append(
                        f"{idx}-savol: To'g'ri javob varianti noto'g'ri variantlardan 3 baravar uzunroq (Length Bias)."
                    )

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def suggest_game_modes(
    student_count: int,
    duration_minutes: int,
    learning_goal: str = "general",
) -> list[dict[str, Any]]:
    """
    DOC-72 Section 2.2: Recommends 2-3 suitable game modes based on class constraints.
    """
    suggestions = []

    if student_count >= 10:
        suggestions.append({
            "mode_id": "team_battle",
            "name": "Team Battle (Jamoaviy jang)",
            "reason": "Katta sinf uchun hamkorlik va jamoaviy ruhni oshirish uchun ideal.",
        })

    if duration_minutes <= 10:
        suggestions.append({
            "mode_id": "speed_run",
            "name": "Speed Run Time Attack",
            "reason": "Qisqa 5-10 daqiqalik tezkor dars tekshiruvi uchun qulay.",
        })
    else:
        suggestions.append({
            "mode_id": "gold_quest",
            "name": "Gold Quest (Oltin Sandiqlar)",
            "reason": "Resurslarni boshqarish va yuqori motivatsiya beruvchi 15-20 daqiqalik o'yin.",
        })

    # Always provide Classic Quiz
    suggestions.append({
        "mode_id": "classic",
        "name": "Classic Speed & Accuracy",
        "reason": "Universal tezlik va bilim poygasi.",
    })

    return suggestions[:3]


def lock_question(quiz_id: str, question_id: str, is_locked: bool = True) -> bool:
    """
    DOC-66 Section 5: Locks/unlocks a question to protect it from AI modifications.
    """
    try:
        from apps.quizzes.models import Question
        q = Question.objects.filter(id=question_id, quiz_id=quiz_id).first()
        if q:
            q.is_locked = is_locked
            q.save(update_fields=["is_locked"])
            return True
    except Exception as e:
        logger.debug(f"Could not update question lock in DB: {e}")
    return False
