"""Pricing abstraction and cost estimation for embedding models."""

# Cost per 1,000,000 tokens in USD
_DEFAULT_RATES_PER_MILLION_TOKENS: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
    "local": 0.0,
    "mock": 0.0,
}


class EmbeddingPricing:
    """Estimates financial cost of embedding requests based on token volume.

    Returns None when pricing data is unavailable, adhering to the contract
    that cost must never be guessed or hallucinated.
    """

    @classmethod
    def estimate_cost(
        cls,
        model: str,
        total_tokens: int,
        provider: str | None = None,
    ) -> float | None:
        """Estimate cost in USD for total_tokens.

        Returns:
            float: Cost in USD if model rate is known.
            None: If model rate is unknown.
        """
        if total_tokens <= 0:
            return 0.0

        if provider in ("local", "mock"):
            return 0.0

        clean_model = model.lower().strip()
        rate = _DEFAULT_RATES_PER_MILLION_TOKENS.get(clean_model)
        if rate is None:
            return None

        return (total_tokens / 1_000_000.0) * rate
