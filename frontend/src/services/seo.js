export function safeMetadataText(value, maxLength = 160) {
  return Array.from(String(value ?? ""))
    .filter((character) => {
      const code = character.charCodeAt(0);
      return code >= 32 && code !== 127 && character !== "<" && character !== ">";
    })
    .join("")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}
