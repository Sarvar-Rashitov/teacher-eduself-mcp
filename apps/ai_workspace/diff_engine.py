from typing import Optional, Any
from copy import deepcopy


class AIDiffEngine:
    """
    DOC-66 Section 4: Computes Before/After side-by-side diffs for AI-proposed
    question modifications and guarantees strict protection for locked questions.
    """

    @classmethod
    def compute_diff(
        cls,
        original_questions: list[dict[str, Any]],
        proposed_questions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Computes structured diff between original and proposed question sets.
        """
        orig_map = {q.get("order", idx + 1): q for idx, q in enumerate(original_questions)}
        prop_map = {q.get("order", idx + 1): q for idx, q in enumerate(proposed_questions)}

        added: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        modified: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []
        blocked_modifications: list[dict[str, Any]] = []

        all_orders = sorted(set(orig_map.keys()) | set(prop_map.keys()))

        for order in all_orders:
            orig = orig_map.get(order)
            prop = prop_map.get(order)

            if orig is None and prop is not None:
                added.append(prop)
            elif orig is not None and prop is None:
                if orig.get("is_locked"):
                    blocked_modifications.append({
                        "order": order,
                        "reason": "Attempted to delete locked question",
                        "original": orig,
                    })
                    unchanged.append(orig)
                else:
                    removed.append(orig)
            else:
                # Both exist: check for changes
                changed_fields = cls._detect_changed_fields(orig, prop)
                if not changed_fields:
                    unchanged.append(orig)
                else:
                    if orig.get("is_locked"):
                        blocked_modifications.append({
                            "order": order,
                            "reason": "Attempted to modify locked question",
                            "changed_fields": changed_fields,
                            "original": orig,
                            "proposed": prop,
                        })
                        unchanged.append(orig)
                    else:
                        modified.append({
                            "order": order,
                            "old": orig,
                            "new": prop,
                            "changed_fields": changed_fields,
                        })

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
            "blocked_modifications": blocked_modifications,
            "total_changes": len(added) + len(removed) + len(modified),
        }

    @classmethod
    def apply_diff(
        cls,
        original_questions: list[dict[str, Any]],
        proposed_questions: list[dict[str, Any]],
        accepted_orders: Optional[set[int]] = None,
    ) -> list[dict[str, Any]]:
        """
        Applies approved proposed modifications while strictly preserving
        any question with is_locked=True.
        """
        orig_map = {q.get("order", idx + 1): deepcopy(q) for idx, q in enumerate(original_questions)}
        prop_map = {q.get("order", idx + 1): deepcopy(q) for idx, q in enumerate(proposed_questions)}

        result: list[dict[str, Any]] = []
        all_orders = sorted(set(orig_map.keys()) | set(prop_map.keys()))

        for order in all_orders:
            orig = orig_map.get(order)
            prop = prop_map.get(order)

            # Locked question guarantee: NEVER overwrite or delete
            if orig and orig.get("is_locked"):
                result.append(orig)
                continue

            if accepted_orders is not None and order not in accepted_orders:
                # If teacher did not accept this change, keep original (if existed)
                if orig:
                    result.append(orig)
                continue

            if prop is not None:
                result.append(prop)

        # Normalize sequential ordering
        for idx, q in enumerate(result, start=1):
            q["order"] = idx

        return result

    @staticmethod
    def _detect_changed_fields(orig: dict[str, Any], prop: dict[str, Any]) -> list[str]:
        keys = ["prompt", "type", "options", "correct_answer", "explanation", "points", "time_limit_seconds"]
        changed = []
        for k in keys:
            if orig.get(k) != prop.get(k):
                changed.append(k)
        return changed
