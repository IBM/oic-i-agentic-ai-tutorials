TIER_WEIGHTS = {
    "standard": 10,
    "premium": 20,
    "strategic": 35,
}


def score_customer_priority(
    customer_id: str,
    tier: str,
    open_support_tickets: int,
    days_since_last_contact: int,
    contract_value_usd: float,
    recent_nps: int | None,
) -> dict[str, object]:
    reasons: list[str] = []
    score = TIER_WEIGHTS[tier]

    if tier == "strategic":
        reasons.append("Strategic account")
    elif tier == "premium":
        reasons.append("Premium account")

    if open_support_tickets:
        ticket_score = min(open_support_tickets * 12, 30)
        score += ticket_score
        reasons.append(f"{open_support_tickets} open support ticket(s)")

    if days_since_last_contact >= 30:
        score += 15
        reasons.append("No recent customer contact")
    elif days_since_last_contact >= 14:
        score += 8
        reasons.append("Follow-up window is approaching")

    if contract_value_usd >= 250000:
        score += 15
        reasons.append("High contract value")
    elif contract_value_usd >= 50000:
        score += 8
        reasons.append("Material contract value")

    if recent_nps is not None:
        if recent_nps <= 6:
            score += 15
            reasons.append("Recent NPS indicates risk")
        elif recent_nps >= 9:
            score -= 5
            reasons.append("Recent NPS is strong")

    priority_score = max(0, min(100, score))
    if priority_score >= 70:
        priority = "high"
        recommended_action = "Schedule executive follow-up within one business day."
    elif priority_score >= 40:
        priority = "medium"
        recommended_action = "Assign an owner and follow up this week."
    else:
        priority = "low"
        recommended_action = "Keep in standard nurture workflow."

    if not reasons:
        reasons.append("No elevated risk signals")

    return {
        "customer_id": customer_id,
        "priority_score": priority_score,
        "priority": priority,
        "recommended_action": recommended_action,
        "reasons": reasons,
    }
