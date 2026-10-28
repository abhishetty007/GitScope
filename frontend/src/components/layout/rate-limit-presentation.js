const GITHUB_UPSTREAM_LIMIT = "GitHub rate limit exceeded. Try again later.";

const APPLICATION_LIMITS = new Map([
  [
    "Too many GitHub requests. Try again later.",
    {
      title: "GitScope request limit reached",
      detail: "GitScope received too many requests in a short period. Wait briefly, then retry.",
    },
  ],
  [
    "GitHub service capacity is temporarily exhausted. Try again later.",
    {
      title: "GitScope service capacity reached",
      detail: "GitScope is temporarily limiting repository analyses to protect shared service capacity. Wait briefly, then retry.",
    },
  ],
  [
    "GitHub request budget temporarily exhausted. Try again later.",
    {
      title: "GitScope service capacity reached",
      detail: "GitScope has temporarily reached its shared GitHub request budget. Wait briefly, then retry.",
    },
  ],
]);

export function getRateLimitPresentation(status, message, retryAfter) {
  let presentation;
  if (status === 429 && message === GITHUB_UPSTREAM_LIMIT) {
    presentation = {
      title: "GitHub rate limit reached",
      detail: "GitHub is temporarily limiting requests. Wait a moment, then retry this analysis.",
    };
  } else if (status === 429 && APPLICATION_LIMITS.has(message)) {
    presentation = APPLICATION_LIMITS.get(message);
  } else {
    presentation = {
      title: "Request limit reached",
      detail: "This request was limited. Wait briefly, then retry.",
    };
  }

  const retrySeconds = Number(retryAfter);
  if (Number.isSafeInteger(retrySeconds) && retrySeconds > 0 && retrySeconds <= 3600) {
    return { ...presentation, detail: `${presentation.detail} Retry in ${retrySeconds} seconds.` };
  }
  return presentation;
}
